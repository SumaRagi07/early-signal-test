import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:provider/provider.dart';
import '../services/app_state.dart';
import 'package:google_fonts/google_fonts.dart';
import '../services/illness_map_service.dart';
import '../models/illness_map_data.dart';
import 'home_screen.dart';
import 'pie_chart_page.dart';
import 'dart:ui' as ui;
import 'dart:typed_data';
import 'dart:convert';
import 'dart:math' as math;
import 'package:http/http.dart' as http;

class CurrentIllnessMapPage extends StatefulWidget {
  const CurrentIllnessMapPage({Key? key}) : super(key: key);

  @override
  State<CurrentIllnessMapPage> createState() => _CurrentIllnessMapPageState();
}

class _CurrentIllnessMapPageState extends State<CurrentIllnessMapPage> {
  GoogleMapController? _mapController;
  Set<Marker> _markers = {};
  List<IllnessMapPoint> _illnessData = [];
  bool _isLoading = true;
  String? _error;
  bool _isFullscreen = false;
  bool _showCategoryPanel = false;

  // ✨ Store all categories by location for multi-category popups
  Map<String, Map<String, List<IllnessMapPoint>>> _locationCategoryData = {};

  // All 6 categories included
  Set<String> _selectedCategories = {
    'airborne', 'direct contact', 'foodborne', 'insect-borne', 'other', 'waterborne'
  };

  @override
  void initState() {
    super.initState();
    _loadMapData();
  }

  Future<void> _loadMapData() async {
    print('🚀 Starting to load map data...');
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
      print('📞 Calling IllnessMapService...');
      final data = await IllnessMapService.getCurrentIllnessMapData(
        userLatitude: position!.latitude,
        userLongitude: position.longitude,
      );

      print('📊 Received data: ${data?.length} points');

      setState(() {
        _illnessData = data ?? [];
        print('💾 Stored ${_illnessData.length} illness data points');
        _isLoading = false; // ✨ Set loading false before creating markers
      });

      // ✨ Create markers AFTER loading is false (so overlay disappears)
      await _createMarkers();

      Future.delayed(const Duration(milliseconds: 500), () {
        _centerOnUserLocation();
      });

    } catch (e) {
      print('💥 Exception in _loadMapData: $e');
      setState(() {
        _error = 'Error loading map data: $e';
        _isLoading = false;
      });
    }
  }

  Future<void> _createMarkers() async {
    print('🎨 Creating separate bubble markers from ${_illnessData.length} data points...');

    final appState = Provider.of<AppState>(context, listen: false);
    final position = appState.currentPosition;

    // Group by location first, then separate by category
    final Map<String, List<IllnessMapPoint>> locationGroups = {};

    for (final point in _illnessData) {
      if (!_selectedCategories.contains(point.category.toLowerCase())) continue;

      final locationKey = '${point.latitude.toStringAsFixed(4)}_${point.longitude.toStringAsFixed(4)}';
      locationGroups.putIfAbsent(locationKey, () => []);
      locationGroups[locationKey]!.add(point);
    }

    print('📍 Found ${locationGroups.length} unique locations');

    final markers = <Marker>{};

    // Clear and rebuild location category data
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

    // Process each location and create smart cluster layout
    for (final entry in locationGroups.entries) {
      final locationKey = entry.key;
      final pointsAtLocation = entry.value;

      // Group by category at this location
      final Map<String, List<IllnessMapPoint>> categoryGroups = {};
      for (final point in pointsAtLocation) {
        categoryGroups.putIfAbsent(point.category, () => []);
        categoryGroups[point.category]!.add(point);
      }

      // ✨ Store all category data for this location
      _locationCategoryData[locationKey] = categoryGroups;

      final categories = categoryGroups.keys.toList();
      final baseLocation = pointsAtLocation.first;

      // ✨ Use location_name from the data (no more geocoding!)
      final locationName = baseLocation.locationName;

      print('📌 Creating ${categories.length} separate bubbles at $locationName');

      // Create smart cluster layout for multiple categories
      for (int i = 0; i < categories.length; i++) {
        final category = categories[i];
        final categoryPoints = categoryGroups[category]!;
        final totalCases = categoryPoints.fold(0, (sum, point) => sum + point.caseCount);

        LatLng markerPosition = _calculateClusterPosition(
            baseLocation.latitude,
            baseLocation.longitude,
            i,
            categories.length
        );

        // Create bubble marker
        final bubbleIcon = await _createCustomBubbleMarker(category, totalCases);

        print('   📍 Creating ${category} bubble with ${totalCases} cases at cluster position ${i + 1}');

        markers.add(
          Marker(
            markerId: MarkerId('${locationKey}_${category}'),
            position: markerPosition,
            icon: bubbleIcon,
            anchor: const Offset(0.5, 0.5),
            infoWindow: InfoWindow(
              title: '${totalCases} case${totalCases > 1 ? 's' : ''} - ${category.toUpperCase()}',
              snippet: '$locationName • Tap again to view details', // ✨ Now shows actual location name
              onTap: () => _showLocationDetailsWithAllCategories(locationKey, locationName, category),
            ),
          ),
        );
      }
    }

    print('✅ Created ${markers.length} markers (${markers.length - 1} clustered illness bubbles + 1 user pin)');

    setState(() {
      _markers = markers;
    });
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

  Future<BitmapDescriptor> _createCustomBubbleMarker(String category, int caseCount) async {
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

    paint.color = color.withOpacity(0.8);
    canvas.drawCircle(Offset(size/2, size/2), size/2, paint);

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
        LatLng(baseLat, baseLng - offsetDistance), // Left
        LatLng(baseLat, baseLng + offsetDistance), // Right
      ];
      return positions[index];

    } else if (totalCount == 3) {
      offsetDistance = 0.0015;
      final positions = [
        LatLng(baseLat + offsetDistance * 0.6, baseLng), // Top
        LatLng(baseLat - offsetDistance * 0.3, baseLng - offsetDistance * 0.5), // Bottom left
        LatLng(baseLat - offsetDistance * 0.3, baseLng + offsetDistance * 0.5), // Bottom right
      ];
      return positions[index];

    } else if (totalCount == 4) {
      offsetDistance = 0.0012;
      final positions = [
        LatLng(baseLat + offsetDistance, baseLng - offsetDistance), // Top left
        LatLng(baseLat + offsetDistance, baseLng + offsetDistance), // Top right
        LatLng(baseLat - offsetDistance, baseLng - offsetDistance), // Bottom left
        LatLng(baseLat - offsetDistance, baseLng + offsetDistance), // Bottom right
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

  void _showLocationDetailsWithAllCategories(String locationKey, String locationName, String tappedCategory) {
    final allCategoriesAtLocation = _locationCategoryData[locationKey] ?? {};

    // If only one category at this location, show single category view
    if (allCategoriesAtLocation.length == 1) {
      final categoryPoints = allCategoriesAtLocation[tappedCategory] ?? [];
      _showSingleCategoryDetails(categoryPoints, locationName, tappedCategory);
      return;
    }

    // Multiple categories - show ALL categories at this location
    _showMultiCategoryDetails(allCategoriesAtLocation, locationName, tappedCategory);
  }

  void _showSingleCategoryDetails(List<IllnessMapPoint> points, String locationName, String category) {
    // ✨ Calculate recent cases for high activity warning
    final recentCases = _getRecentCasesForCategory(points, category);
    final showHighActivityWarning = recentCases >= 4;

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
                        _getCategoryIcon(category),
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
                          '${category.toUpperCase()} Cases in $locationName',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: _getCategoryColor(category),
                          ),
                        ),
                        Text(
                          '${points.fold(0, (sum, p) => sum + p.caseCount)} total ${category.toLowerCase()} cases',
                          style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                        ),
                      ],
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 20),

              // ✨ HIGH ACTIVITY WARNING
              if (showHighActivityWarning)
                Container(
                  margin: const EdgeInsets.only(bottom: 16),
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.orange.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(
                      color: Colors.orange.withOpacity(0.3),
                      width: 2,
                    ),
                  ),
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: Colors.orange,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: const Icon(
                          Icons.warning_amber_rounded,
                          color: Colors.white,
                          size: 24,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'HIGH ACTIVITY ALERT',
                              style: TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.bold,
                                color: Colors.orange,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '$recentCases ${category.toLowerCase()} cases reported here in the last 14 days',
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.grey[700],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),

              Expanded(
                child: ListView.builder(
                  controller: scrollController,
                  itemCount: points.length,
                  itemBuilder: (context, index) {
                    final point = points[index];

                    // ✨ Check if this specific point is recent (within 14 days)
                    final now = DateTime.now();
                    final fourteenDaysAgo = now.subtract(const Duration(days: 14));
                    final isRecent = !point.reportTimestamp.isBefore(fourteenDaysAgo);

                    return Container(
                      margin: const EdgeInsets.only(bottom: 16),
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: _getCategoryColor(point.category).withOpacity(0.08),
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(
                          color: isRecent
                              ? _getCategoryColor(point.category).withOpacity(0.4)  // ✨ Stronger border if recent
                              : _getCategoryColor(point.category).withOpacity(0.2),
                          width: isRecent ? 2.0 : 1.5,  // ✨ Thicker border if recent
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: _getCategoryColor(point.category).withOpacity(0.1),
                            blurRadius: 8,
                            offset: const Offset(0, 2),
                          ),
                        ],
                      ),
                      child: Row(
                        children: [
                          Container(
                            width: 60,
                            height: 60,
                            decoration: BoxDecoration(
                              color: _getCategoryColor(point.category),
                              shape: BoxShape.circle,
                              boxShadow: [
                                BoxShadow(
                                  color: _getCategoryColor(point.category).withOpacity(0.3),
                                  blurRadius: 8,
                                  offset: const Offset(0, 4),
                                ),
                              ],
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
                                Row(
                                  children: [
                                    Text(
                                      point.category.toUpperCase(),
                                      style: TextStyle(
                                        fontWeight: FontWeight.bold,
                                        fontSize: 16,
                                        color: _getCategoryColor(point.category),
                                      ),
                                    ),
                                    // ✨ Show badge if recent
                                    if (isRecent) ...[
                                      const SizedBox(width: 8),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                        decoration: BoxDecoration(
                                          color: Colors.orange,
                                          borderRadius: BorderRadius.circular(8),
                                        ),
                                        child: const Text(
                                          'RECENT',
                                          style: TextStyle(
                                            color: Colors.white,
                                            fontSize: 9,
                                            fontWeight: FontWeight.bold,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ],
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  '${point.caseCount} case${point.caseCount > 1 ? 's' : ''} reported',
                                  style: TextStyle(
                                    color: Colors.grey[600],
                                    fontSize: 14,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Row(
                                  children: [
                                    Icon(Icons.access_time, size: 14, color: Colors.grey[500]),
                                    const SizedBox(width: 4),
                                    Text(
                                      'Reported ${_formatDate(point.reportTimestamp)}',
                                      style: TextStyle(
                                        fontSize: 12,
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
                              style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.bold,
                                fontSize: 16,
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
                  child: const Text(
                    'Close',
                    style: TextStyle(
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
      ),
    );
  }

  void _showMultiCategoryDetails(Map<String, List<IllnessMapPoint>> allCategories, String locationName, String tappedCategory) {
    int totalCasesAllCategories = 0;
    for (final categoryPoints in allCategories.values) {
      totalCasesAllCategories += categoryPoints.fold(0, (sum, point) => sum + point.caseCount);
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
                        const Text(
                          'Multiple Cases at this Location',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: Color(0xFF497CCE),
                          ),
                        ),
                        Text(
                          'There are ${allCategories.length} different illness categories with $totalCasesAllCategories total cases at $locationName',
                          style: TextStyle(fontSize: 14, color: Colors.grey[600]),
                        ),
                      ],
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 20),

              Expanded(
                child: ListView.builder(
                  controller: scrollController,
                  itemCount: allCategories.length,
                  itemBuilder: (context, categoryIndex) {
                    final category = allCategories.keys.elementAt(categoryIndex);
                    final categoryPoints = allCategories[category]!;
                    final categoryTotalCases = categoryPoints.fold(0, (sum, point) => sum + point.caseCount);
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
                        boxShadow: [
                          BoxShadow(
                            color: isHighlighted
                                ? _getCategoryColor(category).withOpacity(0.15)
                                : Colors.black.withOpacity(0.05),
                            blurRadius: 8,
                            offset: const Offset(0, 2),
                          ),
                        ],
                      ),
                      child: ExpansionTile(
                        leading: Container(
                          width: 50,
                          height: 50,
                          decoration: BoxDecoration(
                            color: _getCategoryColor(category),
                            shape: BoxShape.circle,
                            boxShadow: [
                              BoxShadow(
                                color: _getCategoryColor(category).withOpacity(0.3),
                                blurRadius: 6,
                                offset: const Offset(0, 3),
                              ),
                            ],
                          ),
                          child: Icon(
                            _getCategoryIcon(category),
                            color: Colors.white,
                            size: 24,
                          ),
                        ),
                        title: Text(
                          category.toUpperCase(),
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                            color: _getCategoryColor(category),
                          ),
                        ),
                        subtitle: Text(
                          '$categoryTotalCases case${categoryTotalCases > 1 ? 's' : ''} reported',
                          style: TextStyle(
                            color: Colors.grey[600],
                            fontSize: 14,
                          ),
                        ),
                        trailing: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                          decoration: BoxDecoration(
                            color: _getCategoryColor(category),
                            borderRadius: BorderRadius.circular(16),
                          ),
                          child: Text(
                            '$categoryTotalCases',
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                              fontSize: 14,
                            ),
                          ),
                        ),
                        children: categoryPoints.map((point) {
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
                                        '${point.caseCount} case${point.caseCount > 1 ? 's' : ''}',
                                        style: TextStyle(
                                          fontWeight: FontWeight.w600,
                                          fontSize: 14,
                                          color: _getCategoryColor(category),
                                        ),
                                      ),
                                      const SizedBox(height: 4),
                                      Row(
                                        children: [
                                          Icon(Icons.access_time, size: 12, color: Colors.grey[500]),
                                          const SizedBox(width: 4),
                                          Text(
                                            'Reported ${_formatDate(point.reportTimestamp)}',
                                            style: TextStyle(
                                              fontSize: 11,
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
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontWeight: FontWeight.bold,
                                      fontSize: 12,
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
                  child: const Text(
                    'Close',
                    style: TextStyle(
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

  // Add this after _formatDate() function
  int _getRecentCasesForCategory(List<IllnessMapPoint> points, String category) {
    final now = DateTime.now();
    final fourteenDaysAgo = now.subtract(const Duration(days: 14));

    int recentCases = 0;
    for (final point in points) {
      final isRecent = !point.reportTimestamp.isBefore(fourteenDaysAgo);
      final isMatchingCategory = point.category.toLowerCase() == category.toLowerCase();

      if (isRecent && isMatchingCategory) {
        recentCases += point.caseCount;
      }
    }
    return recentCases;
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
                style: const TextStyle(
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
                  const Expanded(
                    child: Text(
                      'Filter Categories',
                      style: TextStyle(
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
          _createMarkers();
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
                style: TextStyle(
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

  void _showColorGuide() {
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
                    const Expanded(
                      child: Text(
                        'Color Guide',
                        style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                          color: Color(0xFF497CCE),
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

                const Text(
                  'Illness Categories:',
                  style: TextStyle(
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
                          category.toUpperCase(),
                          style: TextStyle(
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
                    child: const Text(
                      'Got it!',
                      style: TextStyle(
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

  Widget _buildColorGuideButton() {
    return Positioned(
      top: 50,
      left: 16,
      child: GestureDetector(
        onTap: _showColorGuide,
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
          child: const Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.palette, color: Color(0xFF497CCE), size: 16),
              SizedBox(width: 6),
              Text(
                'Colors',
                style: TextStyle(
                  color: Color(0xFF497CCE),
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
                if (!_isFullscreen) _buildHeader(),
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

            if (_isFullscreen) _buildColorGuideButton(),

            _buildZoomControls(),
          ],
        ),
      ),
      bottomNavigationBar: _isFullscreen ? null : _buildBottomNavigation(),
    );
  }

  Widget _buildHeader() {
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
              style: const TextStyle(fontSize: 16),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _loadMapData,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF497CCE),
              ),
              child: const Text(
                'Retry',
                style: TextStyle(color: Colors.white),
              ),
            ),
          ],
        ),
      );
    }

    if (position == null) {
      return const Center(
        child: Text(
          'Location not available',
          style: TextStyle(fontSize: 16),
        ),
      );
    }

    return Stack(
      children: [
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

        // ✨ Loading overlay
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
                        const Text(
                          'Loading Reports',
                          style: TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                            color: Color(0xFF497CCE),
                          ),
                        ),
                        const SizedBox(height: 12),
                        Text(
                          'Fetching illness reports from across the country...',
                          textAlign: TextAlign.center,
                          style: TextStyle(
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