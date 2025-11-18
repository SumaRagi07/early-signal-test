const admin = require('firebase-admin');

// ✨ CRITICAL: Initialize Firebase Admin FIRST (before anything else)
admin.initializeApp();

const { BigQuery } = require('@google-cloud/bigquery');
const functions = require('firebase-functions');
const axios = require('axios');  // ✨ ADD THIS

const bigquery = new BigQuery({ projectId: 'adsp-34002-ip07-early-signal' });

// ✅ Get API key from Firebase config or hardcoded
const GOOGLE_GEOCODING_API_KEY = functions.config().google?.api_key || 'paste key here';

// Verify Firebase authentication
async function verifyFirebaseAuth(req) {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    throw new Error('Unauthorized: Missing or invalid Authorization header');
  }
  const idToken = authHeader.split('Bearer ')[1];
  await admin.auth().verifyIdToken(idToken);
}

// ✨ Extract GPS coordinates from sample_exposure_tag
function extractCoordinates(tag) {
  if (!tag) return null;

  // Pattern: "name_YYYY-MM-DD_LAT_LON"
  const pattern = /_(-?\d+\.\d+)_(-?\d+\.\d+)$/;
  const match = tag.match(pattern);

  if (match) {
    return {
      latitude: parseFloat(match[1]),
      longitude: parseFloat(match[2])
    };
  }
  return null;
}

// ✨ Geocode location to get clean name
async function geocodeLocation(lat, lon) {
  if (!GOOGLE_GEOCODING_API_KEY || GOOGLE_GEOCODING_API_KEY === 'paste key here') {
    console.log('⚠️ Geocoding API key not configured, skipping geocoding');
    return null;
  }

  try {
    const url = `https://maps.googleapis.com/maps/api/geocode/json?latlng=${lat},${lon}&key=${GOOGLE_GEOCODING_API_KEY}`;
    const response = await axios.get(url);

    if (response.data.status === 'OK' && response.data.results.length > 0) {
      const result = response.data.results[0];

      let placeName = '';
      let city = '';
      let state = '';

      for (const component of result.address_components) {
        if (component.types.includes('point_of_interest') ||
            component.types.includes('establishment')) {
          placeName = component.long_name;
        }
        if (component.types.includes('locality')) {
          city = component.long_name;
        }
        if (component.types.includes('administrative_area_level_1')) {
          state = component.short_name;
        }
      }

      // Build formatted name
      let formattedName = placeName || city || 'Unknown Location';
      if (city && state) {
        formattedName = placeName ? `${placeName}, ${city}, ${state}` : `${city}, ${state}`;
      }

      console.log(`✅ Geocoded: ${lat},${lon} → ${formattedName}`);

      return {
        formatted_name: formattedName,
        place_name: placeName,
        city: city,
        state: state
      };
    }

    console.log(`⚠️ Geocoding returned no results for ${lat},${lon}`);
    return null;
  } catch (error) {
    console.error('❌ Geocoding error:', error.message);
    return null;
  }
}

exports.insertUserWithTract = functions.region('us-central1')
  .runWith({ timeoutSeconds: 120, memory: '256MB' })
  .https.onRequest(async (req, res) => {
    // Verify Firebase authentication
    try {
      await verifyFirebaseAuth(req);
    } catch (error) {
      return res.status(401).json({ error: 'Authentication required', details: error.message });
    }

    if (req.method !== 'POST') {
      return res.status(403).json({ error: 'Only POST requests allowed' });
    }

    const { user_id, email, latitude, longitude } = req.body;
    if (!user_id || !email || latitude === undefined || longitude === undefined) {
      return res.status(400).json({ error: 'Missing required fields' });
    }

    try {
      const query = `
        DECLARE user_point GEOGRAPHY;
        DECLARE user_tract_id STRING;

        SET user_point = ST_GEOGPOINT(@longitude, @latitude);

        -- Step 1: Calculate user's tract ID
        SET user_tract_id = IFNULL((
          SELECT geo_id
          FROM \`adsp-34002-ip07-early-signal.tracts.all_tracts\`
          WHERE ST_WITHIN(user_point, tract_geom)
          LIMIT 1
        ), 'unknown');

        -- Step 2: Insert/Update user location
        MERGE \`adsp-34002-ip07-early-signal.user_data_central.user_location_table\` AS target
        USING (
          SELECT
            @user_id AS user_id,
            @email AS email,
            @latitude AS latitude,
            @longitude AS longitude,
            user_point AS current_geopoint,
            user_tract_id AS tract_id,
            TIMESTAMP(DATETIME(CURRENT_TIMESTAMP(), "America/Chicago")) AS timestamp
        ) AS source
        ON target.user_id = source.user_id
        WHEN MATCHED THEN
          UPDATE SET
            email = source.email,
            latitude = source.latitude,
            longitude = source.longitude,
            current_geopoint = source.current_geopoint,
            tract_id = source.tract_id,
            timestamp = source.timestamp
        WHEN NOT MATCHED THEN
          INSERT (user_id, email, latitude, longitude, current_geopoint, tract_id, timestamp)
          VALUES (source.user_id, source.email, source.latitude, source.longitude, source.current_geopoint, source.tract_id, source.timestamp);

        -- Step 3: Clean up old entries
        DELETE FROM \`adsp-34002-ip07-early-signal.user_data_central.user_location_table\`
        WHERE user_id = @user_id
          AND timestamp < (
            SELECT MAX(timestamp)
            FROM \`adsp-34002-ip07-early-signal.user_data_central.user_location_table\`
            WHERE user_id = @user_id
          );

        -- Step 4: Get alerts (hyper-local + major outbreaks)
        SELECT
          exposure_cluster_id,
          cluster_spatial_id,
          sample_exposure_tag,
          cluster_size,
          predominant_disease,
          predominant_disease_count,
          predominant_category,  -- ✨ Category field
          consensus_ratio,
          first_report_ts,
          last_report_ts,
          span_hours,
          distinct_tract_ids,
          distinct_tract_count,
          distinct_state_names,

          -- Flag to identify if alert is in user's tract
          CASE
            WHEN user_tract_id IN UNNEST(distinct_tract_ids) THEN TRUE
            ELSE FALSE
          END AS is_local_to_user,

          -- Create user-friendly alert message
          CONCAT(
            cluster_size, ' people reported ',
            LOWER(predominant_disease),
            CASE
              WHEN sample_exposure_tag IS NOT NULL AND sample_exposure_tag != ''
              THEN CONCAT(' near ', sample_exposure_tag)
              ELSE ' in your area'
            END,
            ' (',
            FORMAT_TIMESTAMP('%m/%d', last_report_ts),
            ')'
          ) AS alert_message

        FROM \`adsp-34002-ip07-early-signal.alerts.test_clusters_alert_view\`

        WHERE
          alert_flag = TRUE
          AND last_report_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
          AND (
            user_tract_id IN UNNEST(distinct_tract_ids)  -- Hyper-local: user's tract
            OR cluster_size >= 20  -- Major outbreaks: 20+ people
          )

        ORDER BY
          CASE WHEN user_tract_id IN UNNEST(distinct_tract_ids) THEN 1 ELSE 2 END,  -- Local first
          cluster_size DESC,  -- Then by size
          last_report_ts DESC  -- Then by recency

        LIMIT 20;
      `;

      const [job] = await bigquery.createQueryJob({
        query,
        location: 'us-central1',
        params: { user_id, email, latitude, longitude },
      });

      const [alerts] = await job.getQueryResults();

      // ✨ Process alerts and geocode locations
      console.log(`📍 Processing ${alerts.length} alerts for geocoding...`);

      const processedAlerts = [];

      for (const alert of alerts) {
        let locationName = '';

        // ✨ Try to geocode if we have coordinates in the tag
        const coords = extractCoordinates(alert.sample_exposure_tag);
        if (coords) {
          console.log(`🗺️ Attempting geocode for: ${alert.sample_exposure_tag}`);
          const geocoded = await geocodeLocation(coords.latitude, coords.longitude);
          if (geocoded) {
            locationName = geocoded.formatted_name;
            console.log(`✅ Geocoded: ${alert.sample_exposure_tag} → ${locationName}`);
          } else {
            console.log(`⚠️ Geocoding failed for: ${alert.sample_exposure_tag}`);
          }
        }

        processedAlerts.push({
          exposure_cluster_id: alert.exposure_cluster_id,
          predominant_disease: alert.predominant_disease,
          predominant_category: alert.predominant_category || 'Other',  // ✨ Category
          sample_exposure_tag: alert.sample_exposure_tag || '',
          location_name: locationName,  // ✨ Geocoded clean name
          cluster_size: alert.cluster_size,
          consensus_ratio: alert.consensus_ratio,
          is_local_to_user: alert.is_local_to_user,
          distinct_tract_count: alert.distinct_tract_count,
          distinct_state_names: alert.distinct_state_names || [],
          alert_message: alert.alert_message,
          last_report_ts: alert.last_report_ts
        });
      }

      // Calculate stats
      const localAlerts = processedAlerts.filter(a => a.is_local_to_user === true);
      const majorAlerts = processedAlerts.filter(a => a.is_local_to_user === false);

      console.log(`✅ Found ${processedAlerts.length} total alerts`);
      console.log(`📍 Hyper-local alerts: ${localAlerts.length}`);
      console.log(`🌆 Major outbreak alerts: ${majorAlerts.length}`);

      if (processedAlerts.length > 0) {
        console.log('🚨 Sample alerts:');
        processedAlerts.slice(0, 3).forEach((alert, i) => {
          const type = alert.is_local_to_user ? 'LOCAL' : 'MAJOR';
          const location = alert.location_name || 'Unknown location';
          console.log(`  ${i+1}. [${type}] ${alert.cluster_size} cases of ${alert.predominant_disease} at ${location}`);
        });
      }

      return res.status(200).json({
        success: true,
        message: `Location updated. Found ${processedAlerts.length} illness report${processedAlerts.length === 1 ? '' : 's'}.`,
        alerts: processedAlerts,  // ✨ Return processed alerts with geocoded names
        alert_count: processedAlerts.length,
        local_alert_count: localAlerts.length,
        major_outbreak_count: majorAlerts.length,
        user_location: { latitude, longitude }
      });

    } catch (error) {
      console.error('🔥 Query Error:', {
        message: error.message,
        code: error.code,
        errors: error.errors
      });

      return res.status(500).json({
        error: 'Failed to fetch illness reports',
        details: error.errors?.[0]?.message || error.message,
      });
    }
  });


exports.getIllnessPieChartData = functions.region('us-central1')
    .runWith({ timeoutSeconds: 60, memory: '256MB' })
    .https.onRequest(async (req, res) => {
      // NEW: Verify Firebase authentication
      try {
        await verifyFirebaseAuth(req);
      } catch (error) {
        return res.status(401).json({ error: 'Authentication required', details: error.message });
      }

      if (req.method !== 'POST') {
        return res.status(403).json({ error: 'Only POST requests allowed' });
      }

      const { latitude, longitude, radius_miles = 5 } = req.body;

      if (latitude === undefined || longitude === undefined) {
        return res.status(400).json({ error: 'Missing latitude or longitude' });
      }

      try {
        const query = `
          WITH nearby_reports AS (
            SELECT
              illness_category,
              final_diagnosis,
              report_timestamp,

              -- ✨ Use current location for AIRBORNE, exposure location for others
              CASE
                WHEN LOWER(illness_category) = 'airborne' THEN
                  ST_DISTANCE(
                    ST_GEOGPOINT(@longitude, @latitude),
                    ST_GEOGPOINT(current_longitude, current_latitude)
                  ) / 1609.34
                ELSE
                  ST_DISTANCE(
                    ST_GEOGPOINT(@longitude, @latitude),
                    ST_GEOGPOINT(exposure_longitude, exposure_latitude)
                  ) / 1609.34
              END AS distance_miles

            FROM \`adsp-34002-ip07-early-signal.illness_tracker.illness_reports_llm\`
            WHERE
              illness_category IS NOT NULL
              AND report_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)

              -- ✨ Airborne: check current location is valid and within radius
              AND (
                (LOWER(illness_category) = 'airborne'
                 AND current_latitude IS NOT NULL
                 AND current_longitude IS NOT NULL
                 AND ST_DISTANCE(
                   ST_GEOGPOINT(@longitude, @latitude),
                   ST_GEOGPOINT(current_longitude, current_latitude)
                 ) / 1609.34 <= @radius_miles)

                -- ✨ Non-airborne: check exposure location is valid and within radius
                OR (LOWER(illness_category) != 'airborne'
                    AND exposure_latitude IS NOT NULL
                    AND exposure_longitude IS NOT NULL
                    AND ST_DISTANCE(
                      ST_GEOGPOINT(@longitude, @latitude),
                      ST_GEOGPOINT(exposure_longitude, exposure_latitude)
                    ) / 1609.34 <= @radius_miles)
              )
          )
          SELECT
            COALESCE(illness_category, 'Unknown') as category,
            COUNT(*) as case_count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
          FROM nearby_reports
          GROUP BY illness_category
          ORDER BY case_count DESC
        `;

        const [job] = await bigquery.createQueryJob({
          query,
          location: 'us-central1',
          params: {
            latitude: parseFloat(latitude),
            longitude: parseFloat(longitude),
            radius_miles: parseFloat(radius_miles)
          },
        });

        const [rows] = await job.getQueryResults();

        console.log(`✅ Pie Chart Data Query successful for location: ${latitude}, ${longitude}`);
        console.log(`📊 Found ${rows.length} illness categories`);
        console.log(`   - Using CURRENT location for airborne cases`);
        console.log(`   - Using EXPOSURE location for non-airborne cases`);

        return res.status(200).json({
          success: true,
          data: rows,
          location: { latitude, longitude, radius_miles },
          total_categories: rows.length,
          total_cases: rows.reduce((sum, row) => sum + parseInt(row.case_count), 0)
        });

      } catch (error) {
        console.error('🔥 getIllnessPieChartData Error:', {
          message: error.message,
          code: error.code,
          errors: error.errors,
        });

        return res.status(500).json({
          error: 'Failed to fetch pie chart data',
          details: error.errors?.[0]?.message || error.message,
        });
      }
    });

    exports.getCurrentIllnessMapData = functions.region('us-central1')
      .runWith({ timeoutSeconds: 60, memory: '256MB' })
      .https.onRequest(async (req, res) => {
        // Verify Firebase authentication
        try {
          await verifyFirebaseAuth(req);
        } catch (error) {
          return res.status(401).json({ error: 'Authentication required', details: error.message });
        }

        if (req.method !== 'POST') {
          return res.status(403).json({ error: 'Only POST requests allowed' });
        }

        const { user_latitude, user_longitude } = req.body;

        if (user_latitude === undefined || user_longitude === undefined) {
          return res.status(400).json({ error: 'Missing user location parameters' });
        }

        try {
          console.log(`🗺️ Fetching map data for user at ${user_latitude}, ${user_longitude}`);

          const query = `
            SELECT
              current_latitude as latitude,
              current_longitude as longitude,
              current_location_name as location_name,  -- ✨ ADD THIS
              illness_category as category,
              COUNT(*) as case_count,
              MAX(report_timestamp) as latest_report
            FROM \`adsp-34002-ip07-early-signal.illness_tracker.illness_reports_llm\`
            WHERE
              current_latitude IS NOT NULL
              AND current_longitude IS NOT NULL
              AND illness_category IS NOT NULL
              AND report_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
            GROUP BY current_latitude, current_longitude, current_location_name, illness_category  -- ✨ ADD current_location_name
            ORDER BY case_count DESC
          `;

          const [job] = await bigquery.createQueryJob({
            query,
            location: 'us-central1',
            params: {
              user_latitude: parseFloat(user_latitude),
              user_longitude: parseFloat(user_longitude)
            },
          });

          const [rows] = await job.getQueryResults();

          console.log(`✅ Map Data Query successful`);
          console.log(`📍 Found ${rows.length} illness map points`);

          // Transform data for frontend
          const mapData = rows.map(row => ({
            latitude: parseFloat(row.latitude),
            longitude: parseFloat(row.longitude),
            location_name: row.location_name || 'Unknown Location',  // ✨ ADD THIS
            category: row.category,
            case_count: parseInt(row.case_count),
            report_timestamp: row.latest_report
          }));

          // Calculate summary statistics
          const totalCases = mapData.reduce((sum, point) => sum + point.case_count, 0);
          const categoryCounts = {};
          mapData.forEach(point => {
            categoryCounts[point.category] = (categoryCounts[point.category] || 0) + point.case_count;
          });

          console.log(`📊 Total cases: ${totalCases}`);
          console.log(`📊 Category breakdown:`, categoryCounts);

          return res.status(200).json({
            success: true,
            data: mapData,
            total_cases: totalCases,
            category_counts: categoryCounts,
            user_location: {
              latitude: parseFloat(user_latitude),
              longitude: parseFloat(user_longitude)
            }
          });

        } catch (error) {
          console.error('🔥 getCurrentIllnessMapData Error:', {
            message: error.message,
            code: error.code,
            errors: error.errors,
          });

          return res.status(500).json({
            error: 'Failed to fetch current illness map data',
            details: error.errors?.[0]?.message || error.message,
          });
        }
      });





      exports.getExposureIllnessMapData = functions.region('us-central1')
        .runWith({ timeoutSeconds: 60, memory: '256MB' })
        .https.onRequest(async (req, res) => {
          // NEW: Verify Firebase authentication
          try {
            await verifyFirebaseAuth(req);
          } catch (error) {
            return res.status(401).json({ error: 'Authentication required', details: error.message });
          }

          if (req.method !== 'POST') {
            return res.status(403).json({ error: 'Only POST requests allowed' });
          }

          const { user_latitude, user_longitude } = req.body;

          if (user_latitude === undefined || user_longitude === undefined) {
            return res.status(400).json({ error: 'Missing user location parameters' });
          }

          try {
            console.log(`🗺️ Fetching EXPOSURE map data for user at ${user_latitude}, ${user_longitude}`);

            const query = `
              SELECT
                exposure_latitude as latitude,
                exposure_longitude as longitude,
                illness_category as category,
                exposure_location_name,
                location_category,
                COUNT(*) as case_count,
                MAX(report_timestamp) as latest_report,
                AVG(days_since_exposure) as avg_days_since_exposure,
                COUNTIF(restaurant_visit = true) as restaurant_cases,
                COUNTIF(outdoor_activity = true) as outdoor_cases,
                COUNTIF(water_exposure = true) as water_cases
              FROM \`adsp-34002-ip07-early-signal.illness_tracker.illness_reports_llm\`
              WHERE
                exposure_latitude IS NOT NULL
                AND exposure_longitude IS NOT NULL
                AND illness_category IS NOT NULL
                AND report_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
              GROUP BY
                exposure_latitude,
                exposure_longitude,
                illness_category,
                exposure_location_name,
                location_category
              ORDER BY case_count DESC
            `;

            const [job] = await bigquery.createQueryJob({
              query,
              location: 'us-central1',
              params: {
                user_latitude: parseFloat(user_latitude),
                user_longitude: parseFloat(user_longitude)
              },
            });

            const [rows] = await job.getQueryResults();

            console.log(`✅ Exposure Map Data Query successful`);
            console.log(`📍 Found ${rows.length} exposure location points`);

            // Transform data for frontend
            const exposureMapData = rows.map(row => ({
              latitude: parseFloat(row.latitude),
              longitude: parseFloat(row.longitude),
              category: row.category,
              case_count: parseInt(row.case_count),
              report_timestamp: row.latest_report,
              exposure_location_name: row.exposure_location_name,
              location_category: row.location_category,
              avg_days_since_exposure: row.avg_days_since_exposure ? parseFloat(row.avg_days_since_exposure) : null,
              restaurant_cases: parseInt(row.restaurant_cases || 0),
              outdoor_cases: parseInt(row.outdoor_cases || 0),
              water_cases: parseInt(row.water_cases || 0)
            }));

            // Calculate summary statistics
            const totalCases = exposureMapData.reduce((sum, point) => sum + point.case_count, 0);
            const categoryCounts = {};
            const locationCategoryCounts = {};

            exposureMapData.forEach(point => {
              categoryCounts[point.category] = (categoryCounts[point.category] || 0) + point.case_count;
              locationCategoryCounts[point.location_category] = (locationCategoryCounts[point.location_category] || 0) + point.case_count;
            });

            console.log(`📊 Total exposure cases: ${totalCases}`);
            console.log(`📊 Illness category breakdown:`, categoryCounts);
            console.log(`📊 Location category breakdown:`, locationCategoryCounts);

            return res.status(200).json({
              success: true,
              data: exposureMapData,
              total_cases: totalCases,
              category_counts: categoryCounts,
              location_category_counts: locationCategoryCounts,
              user_location: {
                latitude: parseFloat(user_latitude),
                longitude: parseFloat(user_longitude)
              }
            });

          } catch (error) {
            console.error('🔥 getExposureIllnessMapData Error:', {
              message: error.message,
              code: error.code,
              errors: error.errors,
            });

            return res.status(500).json({
              error: 'Failed to fetch exposure illness map data',
              details: error.errors?.[0]?.message || error.message,
            });
          }
        });