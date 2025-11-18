class IllnessMapPoint {
  final double latitude;
  final double longitude;
  final String category;
  final int caseCount;
  final DateTime reportTimestamp;

  // ✨ NEW: Current location name (for current illness map)
  final String locationName;

  // ✨ Exposure-specific fields (all optional, for exposure map)
  final String? exposureLocationName;
  final String? locationCategory;
  final double? avgDaysSinceExposure;
  final int? restaurantCases;
  final int? outdoorCases;
  final int? waterCases;

  IllnessMapPoint({
    required this.latitude,
    required this.longitude,
    required this.category,
    required this.caseCount,
    required this.reportTimestamp,
    this.locationName = 'Unknown Location', // ✨ NEW: Default value
    // Optional exposure parameters
    this.exposureLocationName,
    this.locationCategory,
    this.avgDaysSinceExposure,
    this.restaurantCases,
    this.outdoorCases,
    this.waterCases,
  });

  factory IllnessMapPoint.fromJson(Map<String, dynamic> json) {
    // Handle the timestamp format from BigQuery
    DateTime timestamp;
    try {
      final timestampData = json['report_timestamp'];
      if (timestampData is Map && timestampData.containsKey('value')) {
        timestamp = DateTime.parse(timestampData['value'] as String);
      } else if (timestampData is String) {
        timestamp = DateTime.parse(timestampData);
      } else {
        timestamp = DateTime.now();
      }
    } catch (e) {
      print('Error parsing timestamp: $e');
      timestamp = DateTime.now();
    }

    return IllnessMapPoint(
      latitude: (json['latitude'] as num).toDouble(),
      longitude: (json['longitude'] as num).toDouble(),
      category: json['category'] as String? ?? 'other',
      caseCount: json['case_count'] as int? ?? 1,
      reportTimestamp: timestamp,

      // ✨ NEW: Parse location_name (for current illness map)
      locationName: json['location_name'] as String? ?? 'Unknown Location',

      // Parse exposure fields (optional, for exposure map)
      exposureLocationName: json['exposure_location_name'] as String?,
      locationCategory: json['location_category'] as String?,
      avgDaysSinceExposure: json['avg_days_since_exposure'] != null
          ? (json['avg_days_since_exposure'] as num).toDouble()
          : null,
      restaurantCases: json['restaurant_cases'] as int?,
      outdoorCases: json['outdoor_cases'] as int?,
      waterCases: json['water_cases'] as int?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'latitude': latitude,
      'longitude': longitude,
      'category': category,
      'case_count': caseCount,
      'report_timestamp': reportTimestamp.toIso8601String(),

      // ✨ NEW: Include location_name
      'location_name': locationName,

      // Include exposure fields
      'exposure_location_name': exposureLocationName,
      'location_category': locationCategory,
      'avg_days_since_exposure': avgDaysSinceExposure,
      'restaurant_cases': restaurantCases,
      'outdoor_cases': outdoorCases,
      'water_cases': waterCases,
    };
  }
}

class IllnessMapResponse {
  final List<IllnessMapPoint> data;
  final int totalCases;
  final Map<String, int> categoryCounts;
  final Map<String, double> userLocation;
  // Optional location category counts for exposure data
  final Map<String, int>? locationCategoryCounts;

  IllnessMapResponse({
    required this.data,
    required this.totalCases,
    required this.categoryCounts,
    required this.userLocation,
    this.locationCategoryCounts,
  });

  factory IllnessMapResponse.fromJson(Map<String, dynamic> json) {
    try {
      final dataList = json['data'] as List<dynamic>;
      final points = dataList.map((item) {
        try {
          return IllnessMapPoint.fromJson(item);
        } catch (e) {
          print('Error parsing individual point: $e');
          print('Point data: $item');
          return null;
        }
      }).where((point) => point != null).cast<IllnessMapPoint>().toList();

      return IllnessMapResponse(
        data: points,
        totalCases: json['total_cases'] as int? ?? 0,
        categoryCounts: json['category_counts'] != null
            ? Map<String, int>.from(json['category_counts'] as Map)
            : {},
        userLocation: json['user_location'] != null
            ? Map<String, double>.from(json['user_location'] as Map)
            : {},
        // Parse location category counts if available
        locationCategoryCounts: json['location_category_counts'] != null
            ? Map<String, int>.from(json['location_category_counts'] as Map)
            : null,
      );
    } catch (e) {
      print('Error parsing IllnessMapResponse: $e');
      return IllnessMapResponse(
        data: [],
        totalCases: 0,
        categoryCounts: {},
        userLocation: {},
        locationCategoryCounts: null,
      );
    }
  }
}