import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../services/app_state.dart';
import '../services/illness_map_service.dart';
import '../models/illness_map_data.dart';
import 'home_screen.dart';
import 'pie_chart_page.dart';
import 'dart:ui' as ui;
import 'dart:typed_data';
import 'dart:convert';
import 'dart:math' as math;
import 'package:http/http.dart' as http;

class ExposureIllnessMapPage extends StatefulWidget {
  const ExposureIllnessMapPage({Key? key}) : super(key: key);

  @override
  State<ExposureIllnessMapPage> createState() => _ExposureIllnessMapPageState();
}

class _ExposureIllnessMapPageState extends State<ExposureIllnessMapPage> {
  GoogleMapController? _mapController;
  Set<Marker> _markers = {};
  List<IllnessMapPoint> _exposureData = [];
  bool _isLoading = true;
  String? _error;
  bool _isFullscreen = false;
  bool _showCategoryPanel = false;

  // ✨ Store all categories by exposure location for multi-category popups
  Map<String, Map<String, List<IllnessMapPoint>>> _locationCategoryData = {};

  // All 6 categories included
  Set<String> _selectedCategories = {
    'airborne', 'direct contact', 'foodborne', 'insect-borne', 'other', 'waterborne'
  };

  @override
  void initState() {
    super.initState();
    _loadExposureMapData();
  }

  int _getRecentCasesForCategory(List<IllnessMapPoint> points, String category) {
    final now = DateTime.now();
    final fourteenDaysAgo = now.subtract(const Duration(days: 14));

    int recentCases = 0;
    for (final point in points) {
      final isMatchingCategory = point.category.toLowerCase() == category.toLowerCase();
      final isRecent = !point.reportTimestamp.isBefore(fourteenDaysAgo);

      if (isRecent && isMatchingCategory) {
        recentCases += point.caseCount;
      }
    }

    return recentCases;
  }

  Widget _buildHighActivityWarning(int recentCases, String locationName, String category) {
    if (recentCases < 4) return const SizedBox.shrink();

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF3CD),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFFFE066), width: 2),
        boxShadow: [
          BoxShadow(
            color: Colors.orange.withOpacity(0.1),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: const Color(0xFFFF8C00),
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Icon(
              Icons.warning,
              color: Colors.white,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '⚠️ HIGH ACTIVITY ALERT',
                  style: GoogleFonts.montserrat(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: const Color(0xFFD63384),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '$recentCases ${category.toLowerCase()} cases reported here in the last 14 days. Consider avoiding this location for a few days.',
                  style: GoogleFonts.montserrat(
                    fontSize: 11,
                    color: Colors.black87,
                    height: 1.3,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _loadExposureMapData() async {
    print('🚀 Starting to load EXPOSURE map data...');
    final appState = Provider.of<AppState>(context, listen: false);
    final position = appState.currentPosition;

    print('📍 Current position: ${position?.latitude}, ${position?.longitude}');

    if (position?.latitude == null || position?.longitude == null) {
      print('❌ No location available');
      setState(() {
        _error = 'Location not available';
        _isLoading = false;
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      print('📞 Calling IllnessMapService.getExposureIllnessMapData...');
      final data = await IllnessMapService.getExposureIllnessMapData(
        userLatitude: position!.latitude,
        userLongitude: position.longitude,
      );

      print('📊 Received exposure data: ${data?.length} points');

      setState(() {
        _exposureData = data ?? [];
        print('💾 Stored ${_exposureData.length} exposure data points');
        _isLoading = false; // ✨ Set loading false before creating markers
      });

      // ✨ Create markers AFTER loading is false (so overlay disappears)
      await _createExposureMarkers();

      Future.delayed(const Duration(milliseconds: 500), () {
        _centerOnUserLocation();
      });

    } catch (e) {
      print('💥 Exception in _loadExposureMapData: $e');
      setState(() {
        _error = 'Error loading exposure map data: $e';
        _isLoading = false;
      });
    }
  }

  void _centerOnUserLocation() async {
    final appState = Provider.of<AppState>(context, listen: false);
    final position = appState.currentPosition;

    if (_mapController != null && position != null) {
      await _mapController!.animateCamera(
        CameraUpdate.newCameraPosition(
          CameraPosition(
            target: LatLng(position.latitude, position.longitude),
            zoom: 16.0,
          ),
        ),
      );
      print('📍 Centered map on user location: ${position.latitude}, ${position.longitude}');
    }
  }

  void _zoomIn() async {
    if (_mapController != null) {
      await _mapController!.animateCamera(CameraUpdate.zoomIn());
    }
  }

  void _zoomOut() async {
    if (_mapController != null) {
      await _mapController!.animateCamera(CameraUpdate.zoomOut());
    }
  }

  Future<BitmapDescriptor> _createCustomExposureBubbleMarker(String category, int caseCount) async {
    double size = 70.0;
    if (caseCount >= 10) {
      size = 120.0;
    } else if (caseCount >= 5) {
      size = 100.0;
    } else if (caseCount >= 3) {
      size = 85.0;
    }

    final color = _getCategoryColor(category);

    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder);
    final paint = Paint()..isAntiAlias = true;

    paint.color = color.withOpacity(0.2);
    canvas.drawCircle(Offset(size/2 + 3, size/2 + 3), size/2 + 6, paint);

    paint.color = color.withOpacity(0.9);
    canvas.drawCircle(Offset(size/2, size/2), size/2, paint);

    // Diamond shape to indicate exposure location
    paint.color = Colors.white.withOpacity(0.9);
    paint.style = PaintingStyle.fill;
    final diamondSize = size * 0.3;
    final centerX = size / 2;
    final centerY = size / 2;

    final diamondPath = Path();
    diamondPath.moveTo(centerX, centerY - diamondSize / 2);
    diamondPath.lineTo(centerX + diamondSize / 2, centerY);
    diamondPath.lineTo(centerX, centerY + diamondSize / 2);
    diamondPath.lineTo(centerX - diamondSize / 2, centerY);
    diamondPath.close();
    canvas.drawPath(diamondPath, paint);

    paint.color = Colors.white.withOpacity(0.9);
    paint.style = PaintingStyle.stroke;
    paint.strokeWidth = 2.0;
    canvas.drawCircle(Offset(size/2, size/2), size/2 - 1, paint);

    final picture = recorder.endRecording();
    final image = await picture.toImage((size + 12).toInt(), (size + 12).toInt());
    final bytes = await image.toByteData(format: ui.ImageByteFormat.png);

    return BitmapDescriptor.fromBytes(bytes!.buffer.asUint8List());
  }

  Future<BitmapDescriptor> _createUserLocationPinMarker() async {
    const double size = 120.0;

    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder);
    final paint = Paint()..isAntiAlias = true;

    paint.color = Colors.black.withOpacity(0.4);
    canvas.drawCircle(Offset(size/2 + 4, size/2 + 8), size * 0.3, paint);

    final centerX = size / 2;
    final centerY = size * 0.3;
    final radius = size * 0.28;

    final path = Path();
    path.addOval(Rect.fromCircle(center: Offset(centerX, centerY), radius: radius));
    path.moveTo(centerX, centerY + radius);
    path.lineTo(centerX - radius * 0.6, centerY + radius + size * 0.35);
    path.lineTo(centerX + radius * 0.6, centerY + radius + size * 0.35);
    path.close();

    paint.shader = ui.Gradient.radial(
      Offset(centerX, centerY),
      radius,
      [
        const Color(0xFFFF4444),
        const Color(0xFFCC0000),
      ],
    );
    canvas.drawPath(path, paint);

    paint.shader = null;
    paint.color = Colors.white;
    paint.style = PaintingStyle.stroke;
    paint.strokeWidth = 4.0;
    canvas.drawPath(path, paint);

    paint.style = PaintingStyle.fill;
    paint.color = Colors.white;
    canvas.drawCircle(Offset(centerX, centerY), radius * 0.5, paint);

    paint.color = const Color(0xFFFF0000);
    canvas.drawCircle(Offset(centerX, centerY), radius * 0.25, paint);

    final picture = recorder.endRecording();
    final image = await picture.toImage(size.toInt(), (size * 1.2).toInt());
    final bytes = await image.toByteData(format: ui.ImageByteFormat.png);

    return BitmapDescriptor.fromBytes(bytes!.buffer.asUint8List());
  }

  LatLng _calculateClusterPosition(double baseLat, double baseLng, int index, int totalCount) {
    if (totalCount == 1) {
      return LatLng(baseLat, baseLng);
    }

    double offsetDistance;

    if (totalCount == 2) {
      offsetDistance = 0.0015;
      final positions = [
        LatLng(baseLat, baseLng - offsetDistance),
        LatLng(baseLat, baseLng + offsetDistance),
      ];
      return positions[index];

    } else if (totalCount == 3) {
      offsetDistance = 0.0015;
      final positions = [
        LatLng(baseLat + offsetDistance * 0.6, baseLng),
        LatLng(baseLat - offsetDistance * 0.3, baseLng - offsetDistance * 0.5),
        LatLng(baseLat - offsetDistance * 0.3, baseLng + offsetDistance * 0.5),
      ];
      return positions[index];

    } else if (totalCount == 4) {
      offsetDistance = 0.0012;
      final positions = [
        LatLng(baseLat + offsetDistance, baseLng - offsetDistance),
        LatLng(baseLat + offsetDistance, baseLng + offsetDistance),
        LatLng(baseLat - offsetDistance, baseLng - offsetDistance),
        LatLng(baseLat - offsetDistance, baseLng + offsetDistance),
      ];
      return positions[index];

    } else {
      offsetDistance = 0.0018;
      final angle = (index * 2 * math.pi) / totalCount;
      final offsetLat = baseLat + (offsetDistance * math.cos(angle));
      final offsetLng = baseLng + (offsetDistance * math.sin(angle));
      return LatLng(offsetLat, offsetLng);
    }
  }

  // ✨ FIXED: Create markers for EXPOSURE locations - group by EXACT location + name
  Future<void> _createExposureMarkers() async {
    print('🎨 Creating exposure bubble markers from ${_exposureData.length} data points...');

    final appState = Provider.of<AppState>(context, listen: false);
    final position = appState.currentPosition;

    // ✨ FIX: Group ONLY by coordinates with precision to avoid tiny differences
    final Map<String, List<IllnessMapPoint>> exposureLocationGroups = {};

    for (final point in _exposureData) {
      if (!_selectedCategories.contains(point.category.toLowerCase())) continue;

      // ✨ KEY FIX: Round coordinates to 4 decimal places (~11 meters precision)
      // This groups reports at the same location even if coordinates vary slightly
      final lat = point.latitude.toStringAsFixed(3);
      final lng = point.longitude.toStringAsFixed(3);
      final locationKey = '${lat}_${lng}';

      exposureLocationGroups.putIfAbsent(locationKey, () => []);
      exposureLocationGroups[locationKey]!.add(point);

      print('   🔑 Grouped point to key: $locationKey (${point.category}, ${point.caseCount} cases)');
    }

    print('📍 Found ${exposureLocationGroups.length} unique EXPOSURE locations after grouping');

    final markers = <Marker>{};
    _locationCategoryData.clear();

    // Add user location marker
    if (position != null) {
      final userLocationIcon = await _createUserLocationPinMarker();
      markers.add(
        Marker(
          markerId: const MarkerId('user_location'),
          position: LatLng(position.latitude, position.longitude),
          icon: userLocationIcon,
          anchor: const Offset(0.5, 1.0),
          infoWindow: const InfoWindow(
            title: 'Your Location',
            snippet: 'Current position',
          ),
        ),
      );
      print('📍 Added RED pin marker for user location');
    }

    // Process each EXPOSURE location
    for (final entry in exposureLocationGroups.entries) {
      final locationKey = entry.key;
      final pointsAtLocation = entry.value;

      print('📌 Processing location $locationKey with ${pointsAtLocation.length} reports');

      // Group by category at this exposure location
      final Map<String, List<IllnessMapPoint>> categoryGroups = {};
      for (final point in pointsAtLocation) {
        // ✨ Handle empty category names
        final category = point.category.trim().isEmpty ? 'other' : point.category;
        categoryGroups.putIfAbsent(category, () => []);
        categoryGroups[category]!.add(point);
      }

      _locationCategoryData[locationKey] = categoryGroups;

      final categories = categoryGroups.keys.toList();
      final baseLocation = pointsAtLocation.first;

      // ✨ Get location name from first point that has one
      String locationName = 'Unknown Location';
      for (final point in pointsAtLocation) {
        if (point.exposureLocationName != null && point.exposureLocationName!.trim().isNotEmpty) {
          locationName = point.exposureLocationName!;
          break;
        }
      }

      print('   📍 Location name: $locationName');
      print('   📊 Categories at this location: ${categories.join(', ')}');

      // Create cluster layout for multiple categories
      for (int i = 0; i < categories.length; i++) {
        final category = categories[i];
        final categoryPoints = categoryGroups[category]!;

        // ✨ Sum ALL case counts for this category at this location
        final totalCases = categoryPoints.fold(0, (sum, point) => sum + point.caseCount);

        print('   ✅ Category: $category');
        print('      • ${categoryPoints.length} individual reports');
        print('      • Total cases: $totalCases');

        LatLng markerPosition = _calculateClusterPosition(
            baseLocation.latitude,
            baseLocation.longitude,
            i,
            categories.length
        );

        // Create bubble with TOTAL case count
        final bubbleIcon = await _createCustomExposureBubbleMarker(category, totalCases);

        markers.add(
          Marker(
            markerId: MarkerId('exposure_${locationKey}_${category}'),
            position: markerPosition,
            icon: bubbleIcon,
            anchor: const Offset(0.5, 0.5),
            infoWindow: InfoWindow(
              title: '$totalCases exposure${totalCases > 1 ? 's' : ''} - ${category.toUpperCase()}',
              snippet: '$locationName • Tap to view details',
              onTap: () => _showExposureLocationDetails(locationKey, locationName, category),
            ),
          ),
        );
      }
    }

    print('✅ Created ${markers.length} markers total');
    print('   📊 Breakdown: ${markers.length - 1} illness bubbles + 1 user pin');

    setState(() {
      _markers = markers;
    });
  }

  Color _getCategoryColor(String category) {
    switch (category.toLowerCase()) {
      case 'airborne':
        return const Color(0xFF3B82F6);
      case 'direct contact':
        return const Color(0xFFEF4444);
      case 'foodborne':
        return const Color(0xFFF97316);
      case 'insect-borne':
        return const Color(0xFF10B981);
      case 'waterborne':
        return const Color(0xFF06B6D4);
      case 'other':
        return const Color(0xFF8B5CF6);
      default:
        return const Color(0xFF6B7280);
    }
  }

  IconData _getCategoryIcon(String category) {
    switch (category.toLowerCase()) {
      case 'airborne':
        return Icons.air;
      case 'direct contact':
        return Icons.people;
      case 'foodborne':
        return Icons.restaurant;
      case 'insect-borne':
        return Icons.bug_report;
      case 'waterborne':
        return Icons.water_drop;
      case 'other':
        return Icons.medical_services;
      default:
        return Icons.help_outline;
    }
  }

  void _showExposureLocationDetails(String locationKey, String locationName, String tappedCategory) {
    final allCategoriesAtLocation = _locationCategoryData[locationKey] ?? {};

    if (allCategoriesAtLocation.length == 1) {
      final categoryPoints = allCategoriesAtLocation[tappedCategory] ?? [];
      _showSingleExposureCategoryDetails(categoryPoints, locationName, tappedCategory);
      return;
    }

    _showMultiExposureCategoryDetails(allCategoriesAtLocation, locationName, tappedCategory);
  }

  void _showSingleExposureCategoryDetails(List<IllnessMapPoint> points, String locationName, String category) {
    final recentCases = _getRecentCasesForCategory(points, category);

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.6,
        minChildSize: 0.3,
        maxChildSize: 0.9,
        expand: false,
        builder: (context, scrollController) => Container(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.grey[300],
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(height: 16),

              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: _getCategoryColor(category).withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(
                        Icons.location_on,
                        color: _getCategoryColor(category),
                        size: 24
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${category.toUpperCase()} Exposures at',
                          style: GoogleFonts.montserrat(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: _getCategoryColor(category),
                          ),
                        ),
                        Text(
                          locationName,
                          style: GoogleFonts.montserrat(
                              fontSize: 14,
                              color: Colors.grey[700],
                              fontWeight: FontWeight.w600
                          ),
                        ),
                        Text(
                          '${points.fold(0, (sum, p) => sum + p.caseCount)} people exposed to ${category.toLowerCase()} illness here',
                          style: GoogleFonts.montserrat(
                              fontSize: 10,
                              color: Colors.grey[600]
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 20),

              _buildHighActivityWarning(recentCases, locationName, category),

              Expanded(
                child: ListView.builder(
                  controller: scrollController,
                  itemCount: points.length,
                  itemBuilder: (context, index) {
                    final point = points[index];
                    return Container(
                      margin: const EdgeInsets.only(bottom: 16),
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: _getCategoryColor(point.category).withOpacity(0.08),
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(
                          color: _getCategoryColor(point.category).withOpacity(0.2),
                          width: 1.5,
                        ),
                      ),
                      child: Row(
                        children: [
                          Container(
                            width: 60,
                            height: 60,
                            decoration: BoxDecoration(
                              color: _getCategoryColor(point.category),
                              shape: BoxShape.circle,
                            ),
                            child: Icon(
                              _getCategoryIcon(point.category),
                              color: Colors.white,
                              size: 28,
                            ),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'EXPOSURE: ${point.category.toUpperCase()}',
                                  style: GoogleFonts.montserrat(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 14,
                                    color: _getCategoryColor(point.category),
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  '${point.caseCount} person${point.caseCount > 1 ? 's' : ''} exposed here',
                                  style: GoogleFonts.montserrat(
                                    color: Colors.grey[600],
                                    fontSize: 12,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                if (point.avgDaysSinceExposure != null) ...[
                                  Row(
                                    children: [
                                      Icon(Icons.schedule, size: 12, color: Colors.grey[500]),
                                      const SizedBox(width: 4),
                                      Text(
                                        'Avg ${point.avgDaysSinceExposure!.toStringAsFixed(1)} days since exposure',
                                        style: GoogleFonts.montserrat(
                                          fontSize: 10,
                                          color: Colors.grey[500],
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 4),
                                ],
                                Row(
                                  children: [
                                    Icon(Icons.access_time, size: 12, color: Colors.grey[500]),
                                    const SizedBox(width: 4),
                                    Text(
                                      'Reported ${_formatDate(point.reportTimestamp)}',
                                      style: GoogleFonts.montserrat(
                                        fontSize: 10,
                                        color: Colors.grey[500],
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                            decoration: BoxDecoration(
                              color: _getCategoryColor(point.category),
                              borderRadius: BorderRadius.circular(20),
                            ),
                            child: Text(
                              '${point.caseCount}',
                              style: GoogleFonts.montserrat(
                                color: Colors.white,
                                fontWeight: FontWeight.bold,
                                fontSize: 14,
                              ),
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ),

              const SizedBox(height: 16),

              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () => Navigator.pop(context),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _getCategoryColor(category),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    elevation: 0,
                  ),
                  child: Text(
                    'Close',
                    style: GoogleFonts.montserrat(
                      color: Colors.white,
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showMultiExposureCategoryDetails(Map<String, List<IllnessMapPoint>> allCategories, String locationName, String tappedCategory) {
    int totalExposuresAllCategories = 0;
    for (final categoryPoints in allCategories.values) {
      totalExposuresAllCategories += categoryPoints.fold(0, (sum, point) => sum + point.caseCount);
    }

    String? highActivityCategory;
    int maxRecentCases = 0;
    for (final entry in allCategories.entries) {
      final recentCases = _getRecentCasesForCategory(entry.value, entry.key);
      if (recentCases >= 4 && recentCases > maxRecentCases) {
        maxRecentCases = recentCases;
        highActivityCategory = entry.key;
      }
    }

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        minChildSize: 0.4,
        maxChildSize: 0.95,
        expand: false,
        builder: (context, scrollController) => Container(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.grey[300],
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(height: 16),

              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: const Color(0xFF497CCE).withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(Icons.location_on, color: Color(0xFF497CCE), size: 24),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Multiple Exposure Types',
                          style: GoogleFonts.montserrat(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: const Color(0xFF497CCE),
                          ),
                        ),
                        Text(
                          locationName,
                          style: GoogleFonts.montserrat(
                              fontSize: 14,
                              color: Colors.grey[700],
                              fontWeight: FontWeight.w600
                          ),
                        ),
                        Text(
                          '${allCategories.length} different illness categories with $totalExposuresAllCategories total exposures',
                          style: GoogleFonts.montserrat(
                              fontSize: 12,
                              color: Colors.grey[600]
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 20),

              if (highActivityCategory != null && maxRecentCases >= 4)
                _buildHighActivityWarning(maxRecentCases, locationName, highActivityCategory),

              Expanded(
                child: ListView.builder(
                  controller: scrollController,
                  itemCount: allCategories.length,
                  itemBuilder: (context, categoryIndex) {
                    final category = allCategories.keys.elementAt(categoryIndex);
                    final categoryPoints = allCategories[category]!;
                    final categoryTotalExposures = categoryPoints.fold(0, (sum, point) => sum + point.caseCount);
                    final isHighlighted = category == tappedCategory;

                    return Container(
                      margin: const EdgeInsets.only(bottom: 16),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(
                          color: isHighlighted
                              ? _getCategoryColor(category).withOpacity(0.5)
                              : Colors.grey[200]!,
                          width: isHighlighted ? 2.5 : 1.5,
                        ),
                      ),
                      child: ExpansionTile(
                        leading: Container(
                          width: 50,
                          height: 50,
                          decoration: BoxDecoration(
                            color: _getCategoryColor(category),
                            shape: BoxShape.circle,
                          ),
                          child: Icon(
                            _getCategoryIcon(category),
                            color: Colors.white,
                            size: 24,
                          ),
                        ),
                        title: Text(
                          '${category.toUpperCase()} EXPOSURES',
                          style: GoogleFonts.montserrat(
                            fontWeight: FontWeight.bold,
                            fontSize: 14,
                            color: _getCategoryColor(category),
                          ),
                        ),
                        subtitle: Text(
                          '$categoryTotalExposures person${categoryTotalExposures > 1 ? 's' : ''} exposed',
                          style: GoogleFonts.montserrat(
                            color: Colors.grey[600],
                            fontSize: 12,
                          ),
                        ),
                        trailing: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                          decoration: BoxDecoration(
                            color: _getCategoryColor(category),
                            borderRadius: BorderRadius.circular(16),
                          ),
                          child: Text(
                            '$categoryTotalExposures',
                            style: GoogleFonts.montserrat(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                              fontSize: 12,
                            ),
                          ),
                        ),
                        children: categoryPoints.map<Widget>((point) {
                          return Container(
                            margin: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: _getCategoryColor(category).withOpacity(0.05),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(
                                color: _getCategoryColor(category).withOpacity(0.1),
                              ),
                            ),
                            child: Row(
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        '${point.caseCount} exposure${point.caseCount > 1 ? 's' : ''}',
                                        style: GoogleFonts.montserrat(
                                          fontWeight: FontWeight.w600,
                                          fontSize: 12,
                                          color: _getCategoryColor(category),
                                        ),
                                      ),
                                      const SizedBox(height: 4),
                                      if (point.avgDaysSinceExposure != null) ...[
                                        Row(
                                          children: [
                                            Icon(Icons.schedule, size: 10, color: Colors.grey[500]),
                                            const SizedBox(width: 4),
                                            Text(
                                              'Avg ${point.avgDaysSinceExposure!.toStringAsFixed(1)} days since exposure',
                                              style: GoogleFonts.montserrat(
                                                fontSize: 9,
                                                color: Colors.grey[500],
                                              ),
                                            ),
                                          ],
                                        ),
                                        const SizedBox(height: 2),
                                      ],
                                      Row(
                                        children: [
                                          Icon(Icons.access_time, size: 10, color: Colors.grey[500]),
                                          const SizedBox(width: 4),
                                          Text(
                                            'Reported ${_formatDate(point.reportTimestamp)}',
                                            style: GoogleFonts.montserrat(
                                              fontSize: 9,
                                              color: Colors.grey[500],
                                            ),
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: _getCategoryColor(category),
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  child: Text(
                                    '${point.caseCount}',
                                    style: GoogleFonts.montserrat(
                                      color: Colors.white,
                                      fontWeight: FontWeight.bold,
                                      fontSize: 10,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          );
                        }).toList(),
                      ),
                    );
                  },
                ),
              ),

              const SizedBox(height: 16),

              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () => Navigator.pop(context),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF497CCE),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    elevation: 0,
                  ),
                  child: Text(
                    'Close',
                    style: GoogleFonts.montserrat(
                      color: Colors.white,
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final difference = now.difference(date);

    if (difference.inDays > 7) {
      return '${difference.inDays} days ago';
    } else if (difference.inDays > 0) {
      return '${difference.inDays} day${difference.inDays > 1 ? 's' : ''} ago';
    } else if (difference.inHours > 0) {
      return '${difference.inHours} hour${difference.inHours > 1 ? 's' : ''} ago';
    } else {
      return 'Recently';
    }
  }

  Widget _buildFilterButton() {
    return Positioned(
      top: 140,
      left: 16,
      child: GestureDetector(
        onTap: () {
          setState(() {
            _showCategoryPanel = !_showCategoryPanel;
          });
        },
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            color: const Color(0xFF497CCE),
            borderRadius: BorderRadius.circular(25),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.2),
                blurRadius: 8,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.tune, color: Colors.white, size: 20),
              const SizedBox(width: 8),
              Text(
                'Filters (${_selectedCategories.length})',
                style: GoogleFonts.montserrat(
                  color: Colors.white,
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildFloatingCategoryPanel() {
    return AnimatedPositioned(
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
      top: _showCategoryPanel ? 185 : -300,
      left: 16,
      right: 16,
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.15),
              blurRadius: 20,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: const BoxDecoration(
                color: Color(0xFF497CCE),
                borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.filter_list, color: Colors.white, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Filter Exposure Categories',
                      style: GoogleFonts.montserrat(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  GestureDetector(
                    onTap: () {
                      setState(() {
                        _showCategoryPanel = false;
                      });
                    },
                    child: Container(
                      padding: const EdgeInsets.all(4),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Icon(Icons.close, color: Colors.white, size: 18),
                    ),
                  ),
                ],
              ),
            ),

            Container(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  Row(
                    children: [
                      Expanded(child: _buildCategoryChip('airborne')),
                      const SizedBox(width: 8),
                      Expanded(child: _buildCategoryChip('direct contact')),
                    ],
                  ),
                  const SizedBox(height: 8),

                  Row(
                    children: [
                      Expanded(child: _buildCategoryChip('foodborne')),
                      const SizedBox(width: 8),
                      Expanded(child: _buildCategoryChip('insect-borne')),
                    ],
                  ),
                  const SizedBox(height: 8),

                  Row(
                    children: [
                      Expanded(child: _buildCategoryChip('other')),
                      const SizedBox(width: 8),
                      Expanded(child: _buildCategoryChip('waterborne')),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCategoryChip(String category) {
    final isSelected = _selectedCategories.contains(category);

    return GestureDetector(
      onTap: () {
        setState(() {
          if (isSelected) {
            _selectedCategories.remove(category);
          } else {
            _selectedCategories.add(category);
          }
          _createExposureMarkers();
        });
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: isSelected
              ? _getCategoryColor(category)
              : Colors.grey[100],
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isSelected
                ? _getCategoryColor(category)
                : Colors.grey[300]!,
            width: 1.5,
          ),
          boxShadow: isSelected ? [
            BoxShadow(
              color: _getCategoryColor(category).withOpacity(0.3),
              blurRadius: 6,
              offset: const Offset(0, 2),
            ),
          ] : null,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              _getCategoryIcon(category),
              size: 16,
              color: isSelected ? Colors.white : Colors.grey[600],
            ),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                category.toUpperCase(),
                style: GoogleFonts.montserrat(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: isSelected ? Colors.white : Colors.grey[700],
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            if (isSelected) ...[
              const SizedBox(width: 4),
              Container(
                width: 16,
                height: 16,
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.3),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.check,
                  size: 12,
                  color: Colors.white,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  void _showExposureColorGuide() {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return Dialog(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
          child: Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: const Color(0xFF497CCE).withOpacity(0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Icon(Icons.palette, color: Color(0xFF497CCE), size: 24),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'Exposure Map Guide',
                        style: GoogleFonts.montserrat(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                          color: const Color(0xFF497CCE),
                        ),
                      ),
                    ),
                    GestureDetector(
                      onTap: () => Navigator.pop(context),
                      child: Container(
                        padding: const EdgeInsets.all(4),
                        decoration: BoxDecoration(
                          color: Colors.grey[100],
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Icon(Icons.close, color: Colors.grey[600], size: 20),
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 20),

                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.red.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.red.withOpacity(0.2)),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.location_on, color: Colors.red, size: 24),
                      SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          'Your Current Location',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 16),

                Text(
                  'Exposure Location Categories:',
                  style: GoogleFonts.montserrat(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: Colors.grey,
                  ),
                ),

                const SizedBox(height: 12),

                ...(['airborne', 'direct contact', 'foodborne', 'insect-borne', 'waterborne', 'other'].map((category) {
                  return Container(
                    margin: const EdgeInsets.only(bottom: 8),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: _getCategoryColor(category).withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: _getCategoryColor(category).withOpacity(0.2),
                      ),
                    ),
                    child: Row(
                      children: [
                        Container(
                          width: 24,
                          height: 24,
                          decoration: BoxDecoration(
                            color: _getCategoryColor(category),
                            shape: BoxShape.circle,
                          ),
                          child: Icon(
                            _getCategoryIcon(category),
                            color: Colors.white,
                            size: 14,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Text(
                          '${category.toUpperCase()} EXPOSURES',
                          style: GoogleFonts.montserrat(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                            color: _getCategoryColor(category),
                          ),
                        ),
                      ],
                    ),
                  );
                }).toList()),

                const SizedBox(height: 20),

                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: () => Navigator.pop(context),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF497CCE),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      elevation: 0,
                    ),
                    child: Text(
                      'Got it!',
                      style: GoogleFonts.montserrat(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildExposureColorGuideButton() {
    return Positioned(
      top: 50,
      left: 16,
      child: GestureDetector(
        onTap: _showExposureColorGuide,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.95),
            borderRadius: BorderRadius.circular(20),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.1),
                blurRadius: 8,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.palette, color: Color(0xFF497CCE), size: 16),
              const SizedBox(width: 6),
              Text(
                'Guide',
                style: GoogleFonts.montserrat(
                  color: const Color(0xFF497CCE),
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildZoomControls() {
    return Positioned(
      bottom: 120,
      right: 16,
      child: Column(
        children: [
          Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(8),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.2),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Material(
              color: Colors.transparent,
              child: InkWell(
                borderRadius: BorderRadius.circular(8),
                onTap: _zoomIn,
                child: const SizedBox(
                  width: 48,
                  height: 48,
                  child: Icon(
                    Icons.add,
                    color: Color(0xFF497CCE),
                    size: 24,
                  ),
                ),
              ),
            ),
          ),

          const SizedBox(height: 8),

          Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(8),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.2),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Material(
              color: Colors.transparent,
              child: InkWell(
                borderRadius: BorderRadius.circular(8),
                onTap: _zoomOut,
                child: const SizedBox(
                  width: 48,
                  height: 48,
                  child: Icon(
                    Icons.remove,
                    color: Color(0xFF497CCE),
                    size: 24,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final appState = Provider.of<AppState>(context);
    final position = appState.currentPosition;

    return Scaffold(
      backgroundColor: Colors.grey[100],
      body: SafeArea(
        child: Stack(
          children: [
            Column(
              children: [
                if (!_isFullscreen) _buildExposureHeader(),
                Expanded(
                  child: _buildMapContent(position),
                ),
              ],
            ),

            if (!_isFullscreen) _buildFilterButton(),
            if (!_isFullscreen) _buildFloatingCategoryPanel(),

            Positioned(
              top: _isFullscreen ? 70 : 130,
              right: 16,
              child: Container(
                decoration: BoxDecoration(
                  color: const Color(0xFF497CCE),
                  borderRadius: BorderRadius.circular(25),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.2),
                      blurRadius: 8,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: Material(
                  color: Colors.transparent,
                  child: InkWell(
                    borderRadius: BorderRadius.circular(25),
                    onTap: () {
                      setState(() {
                        _isFullscreen = !_isFullscreen;
                        _showCategoryPanel = false;
                      });
                    },
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      child: Icon(
                        _isFullscreen ? Icons.fullscreen_exit : Icons.fullscreen,
                        color: Colors.white,
                        size: 24,
                      ),
                    ),
                  ),
                ),
              ),
            ),

            if (_isFullscreen) _buildExposureColorGuideButton(),

            _buildZoomControls(),
          ],
        ),
      ),
      bottomNavigationBar: _isFullscreen ? null : _buildBottomNavigation(),
    );
  }

  Widget _buildExposureHeader() {
    return Container(
      color: const Color(0xFF497CCE),
      padding: const EdgeInsets.only(top: 16, bottom: 16),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Row(
          children: [
            GestureDetector(
              onTap: () => Navigator.pop(context),
              child: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.arrow_back, color: Colors.white, size: 24),
              ),
            ),

            Expanded(
              child: Center(
                child: SizedBox(
                  height: 70,
                  child: Image.asset(
                    'assets/images/logo2.png',
                    height: 50,
                    color: Colors.white,
                    colorBlendMode: BlendMode.srcIn,
                  ),
                ),
              ),
            ),

            GestureDetector(
              onTap: () {
                // TODO: Add profile navigation
              },
              child: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.account_circle, color: Colors.white, size: 24),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMapContent(position) {
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 64, color: Colors.grey[400]),
            const SizedBox(height: 16),
            Text(
              _error!,
              textAlign: TextAlign.center,
              style: GoogleFonts.montserrat(fontSize: 16),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _loadExposureMapData,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF497CCE),
              ),
              child: Text(
                'Retry',
                style: GoogleFonts.montserrat(color: Colors.white),
              ),
            ),
          ],
        ),
      );
    }

    if (position == null) {
      return Center(
        child: Text(
          'Location not available',
          style: GoogleFonts.montserrat(fontSize: 16),
        ),
      );
    }

    return Stack(
      children: [
        // ✨ The map (always rendered)
        ClipRRect(
          borderRadius: _isFullscreen
              ? BorderRadius.zero
              : const BorderRadius.vertical(top: Radius.circular(20)),
          child: GoogleMap(
            initialCameraPosition: CameraPosition(
              target: LatLng(position.latitude, position.longitude),
              zoom: 16.0,
            ),
            markers: _markers,
            onMapCreated: (GoogleMapController controller) {
              _mapController = controller;
              Future.delayed(const Duration(milliseconds: 100), () {
                _centerOnUserLocation();
              });
            },
            myLocationEnabled: false,
            myLocationButtonEnabled: false,
            zoomControlsEnabled: false,
            mapType: MapType.normal,
            compassEnabled: true,
            rotateGesturesEnabled: true,
            scrollGesturesEnabled: true,
            tiltGesturesEnabled: true,
            zoomGesturesEnabled: true,
          ),
        ),

        // ✨ Loading overlay (shown on top of map)
        if (_isLoading)
          BackdropFilter(
            filter: ui.ImageFilter.blur(sigmaX: 5, sigmaY: 5),
            child: Container(
              color: Colors.black.withOpacity(0.3),
              child: Center(
                child: Card(
                  margin: const EdgeInsets.symmetric(horizontal: 40),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(32),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const CircularProgressIndicator(
                          color: Color(0xFF497CCE),
                          strokeWidth: 3,
                        ),
                        const SizedBox(height: 20),
                        Text(
                          'Loading Reports',
                          style: GoogleFonts.montserrat(
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                            color: const Color(0xFF497CCE),
                          ),
                        ),
                        const SizedBox(height: 12),
                        Text(
                          'Fetching exposure locations from across the country...',
                          textAlign: TextAlign.center,
                          style: GoogleFonts.montserrat(
                            fontSize: 14,
                            color: Colors.grey[600],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildBottomNavigation() {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 20),
      color: const Color(0xFF497CCE),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          GestureDetector(
            onTap: () => Navigator.pushReplacement(
              context,
              MaterialPageRoute(builder: (_) => const HomeScreen()),
            ),
            child: const Icon(Icons.home, color: Colors.white, size: 30),
          ),
          GestureDetector(
            onTap: () => Navigator.pushReplacement(
              context,
              MaterialPageRoute(builder: (_) => const PieChartPage()),
            ),
            child: const Icon(Icons.pie_chart, color: Colors.white, size: 30),
          ),
        ],
      ),
    );
  }
}