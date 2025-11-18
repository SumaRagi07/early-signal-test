import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:geolocator/geolocator.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:math';
import 'dart:ui' as ui;
import 'dart:typed_data';
import 'package:provider/provider.dart';

import 'map_fullscreen.dart';
import 'outbreak_dashboard.dart';
import 'generate_report_screen.dart';
import 'alerts_page.dart';
import '../models/alert_item.dart';
import '../services/app_state.dart';
import '../services/illness_map_service.dart';
import '../models/illness_map_data.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with WidgetsBindingObserver, TickerProviderStateMixin {
  bool _permissionDenied = false;
  bool _permissionPermanentlyDenied = false;
  GoogleMapController? _mapController;
  bool _isRefreshing = false;
  AnimationController? _refreshController;
  AnimationController? _pulseController;

  String _loadingStep = '';
  int _loadingProgress = 0;

  bool _isMapFullscreen = false;
  bool _isLoadingMapData = false;
  List<IllnessMapPoint> _nearbyIllnessData = [];
  Set<Marker> _nearbyMarkers = {};

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);

    _refreshController = AnimationController(
      duration: const Duration(milliseconds: 1000),
      vsync: this,
    );

    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    )..repeat(reverse: true);

    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await _initializeData();
      await _loadNearbyIllnessMap();
    });
  }

  Future<void> _initializeData() async {
    final appState = Provider.of<AppState>(context, listen: false);
    if (!appState.hasInitialData) {
      await _determinePosition();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _mapController?.dispose();
    _refreshController?.dispose();
    _pulseController?.dispose();
    super.dispose();
  }

  Future<void> _determinePosition() async {
    final appState = Provider.of<AppState>(context, listen: false);

    if (!mounted) return;

    appState.setFetching(true);

    setState(() {
      _loadingStep = 'Requesting location permission...';
      _loadingProgress = 10;
    });

    try {
      bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        if (mounted) {
          setState(() {
            _permissionDenied = true;
            _permissionPermanentlyDenied = false;
            _loadingStep = '';
            _loadingProgress = 0;
          });
        }
        return;
      }

      setState(() {
        _loadingStep = 'Checking permissions...';
        _loadingProgress = 25;
      });

      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }

      if (permission == LocationPermission.deniedForever) {
        if (mounted) {
          setState(() {
            _permissionDenied = true;
            _permissionPermanentlyDenied = true;
            _loadingStep = '';
            _loadingProgress = 0;
          });
        }
        return;
      }

      setState(() {
        _loadingStep = 'Getting your location...';
        _loadingProgress = 50;
      });

      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );

      final latLng = LatLng(position.latitude, position.longitude);

      if (mounted) {
        setState(() {
          _loadingStep = 'Finding your neighborhood...';
          _loadingProgress = 70;
        });

        appState.setPosition(latLng);

        setState(() {
          _loadingStep = 'Checking for illness reports...';
          _loadingProgress = 85;
        });

        await _sendUserLocationToCloudFunction(latLng);

        setState(() {
          _loadingStep = 'Done!';
          _loadingProgress = 100;
        });

        await Future.delayed(const Duration(milliseconds: 500));
      }
    } catch (e) {
      print("Error getting location: $e");
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error getting location. Please try again.')),
        );
      }
    } finally {
      if (mounted) {
        appState.setFetching(false);
        setState(() {
          _loadingStep = '';
          _loadingProgress = 0;
        });
      }
    }
  }

  Future<void> _refreshAlerts() async {
    if (_isRefreshing || !mounted) return;

    setState(() {
      _isRefreshing = true;
      _loadingStep = 'Refreshing alerts...';
      _loadingProgress = 50;
    });

    _refreshController?.repeat();

    try {
      final appState = Provider.of<AppState>(context, listen: false);
      final currentPosition = appState.currentPosition;

      if (currentPosition != null && mounted) {
        setState(() {
          _loadingStep = 'Loading nearby illness data...';
          _loadingProgress = 75;
        });

        await Future.wait([
          _sendUserLocationToCloudFunction(currentPosition),
          _loadNearbyIllnessMap(),
        ]);

        setState(() {
          _loadingProgress = 100;
        });

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                appState.alerts.isEmpty
                    ? '✅ All clear! No illness reports in your area right now.'
                    : '✅ Found ${appState.alerts.length} illness report${appState.alerts.length == 1 ? '' : 's'} near you.',
                style: GoogleFonts.montserrat(),
              ),
              backgroundColor: appState.alerts.isEmpty ? Colors.green : Colors.orange,
              duration: const Duration(seconds: 3),
            ),
          );
        }
      }
    } catch (e) {
      print("🔥 Error refreshing alerts: $e");
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('❌ Couldn\'t check for updates. Please try again.'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isRefreshing = false;
          _loadingStep = '';
          _loadingProgress = 0;
        });

        _refreshController?.stop();
        _refreshController?.reset();
      }
    }
  }

  Future<void> _sendUserLocationToCloudFunction(LatLng position) async {
    final appState = Provider.of<AppState>(context, listen: false);
    final user = FirebaseAuth.instance.currentUser;

    if (user == null) {
      print("❌ No user logged in");
      return;
    }

    try {
      print("🌐 Sending location: ${position.latitude}, ${position.longitude}");

      final idToken = await user.getIdToken(true);
      final url = Uri.parse(
        'https://us-central1-adsp-34002-ip07-early-signal.cloudfunctions.net/insertUserWithTract',
      );

      final response = await http.post(
        url,
        headers: {
          'Authorization': 'Bearer $idToken',
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'user_id': user.uid,
          'email': user.email,
          'latitude': position.latitude,
          'longitude': position.longitude,
        }),
      );

      print("📡 Response status: ${response.statusCode}");
      print("📡 Response body: ${response.body}");

      if (response.statusCode == 200) {
        final json = jsonDecode(response.body);
        final List<dynamic> alertList = json['alerts'] ?? [];

        print("🎯 Raw alerts received: ${alertList.length}");
        print("🎯 Alert data: $alertList");

        if (alertList.isNotEmpty) {
          final clusterAlerts = alertList.map((item) {
            print("🔍 Processing alert item: $item");
            return AlertItem(
              exposureClusterId: item['exposure_cluster_id'] ?? '',
              disease: item['predominant_disease'] ?? 'Unknown',
              category: item['predominant_category'] ?? 'Other',
              locationTag: item['sample_exposure_tag'] ?? '',
              locationName: item['location_name'] ?? '',
              clusterSize: item['cluster_size'] ?? 0,
              consensusRatio: (item['consensus_ratio'] ?? 0.0).toDouble(),
              alertMessage: item['alert_message'] ?? '',
              lastReportTime: DateTime.tryParse(item['last_report_ts']?['value'] ?? '') ?? DateTime.now(),
              isLocalToUser: item['is_local_to_user'] ?? false,
              distinctTractCount: item['distinct_tract_count'] ?? 1,
              distinctStateNames: item['distinct_state_names'] != null
                  ? List<String>.from(item['distinct_state_names'])
                  : [],
            );
          }).toList();

          if (mounted) {
            appState.setAlerts(clusterAlerts);
            print("✅ Set ${clusterAlerts.length} alerts in app state");
          }
        } else {
          if (mounted) {
            appState.setAlerts([]);
            print("ℹ️ No alerts in response, clearing app state");
          }
        }
      } else {
        print("❌ HTTP Error: ${response.statusCode} - ${response.body}");
      }
    } catch (e) {
      print('🔥 Exception while sending location: $e');
      print('🔥 Stack trace: ${StackTrace.current}');
    }
  }

  // ✅ FIXED: Load map and always create user marker
  Future<void> _loadNearbyIllnessMap() async {
    final appState = Provider.of<AppState>(context, listen: false);
    final position = appState.currentPosition;

    if (position == null) {
      print('❌ No user position available for illness map');
      return;
    }

    setState(() {
      _isLoadingMapData = true;
    });

    try {
      print('🗺️ Loading nearby illness map data (20 miles)...');

      // ✅ ALWAYS create user location marker first
      await _createUserLocationMarker(position);

      final allData = await IllnessMapService.getCurrentIllnessMapData(
        userLatitude: position.latitude,
        userLongitude: position.longitude,
      );

      if (allData == null || allData.isEmpty) {
        print('ℹ️ No illness data available - showing map with user pin only');
        setState(() {
          _nearbyIllnessData = [];
          // ✅ DON'T clear markers - user pin is already set
          _isLoadingMapData = false;
        });
        return;
      }

      final nearbyData = allData.where((point) {
        final distance = _calculateDistance(
          position.latitude,
          position.longitude,
          point.latitude,
          point.longitude,
        );
        return distance <= 20.0;
      }).toList();

      print('✅ Found ${nearbyData.length} illness points within 20 miles (out of ${allData.length} total)');

      setState(() {
        _nearbyIllnessData = nearbyData;
      });

      // ✅ Now add illness markers on top of user marker
      await _addIllnessMarkers();

    } catch (e) {
      print('❌ Error loading nearby illness map: $e');
      // ✅ Still show user marker even on error
      final appState = Provider.of<AppState>(context, listen: false);
      final position = appState.currentPosition;
      if (position != null) {
        await _createUserLocationMarker(position);
      }
    } finally {
      if (mounted) {
        setState(() {
          _isLoadingMapData = false;
        });
      }
    }
  }

  double _calculateDistance(double lat1, double lon1, double lat2, double lon2) {
    const double earthRadiusMiles = 3958.8;

    final dLat = _toRadians(lat2 - lat1);
    final dLon = _toRadians(lon2 - lon1);

    final a = sin(dLat / 2) * sin(dLat / 2) +
        cos(_toRadians(lat1)) * cos(_toRadians(lat2)) *
            sin(dLon / 2) * sin(dLon / 2);

    final c = 2 * atan2(sqrt(a), sqrt(1 - a));

    return earthRadiusMiles * c;
  }

  double _toRadians(double degree) {
    return degree * pi / 180;
  }

  // ✅ NEW: Create ONLY user location marker
  Future<void> _createUserLocationMarker(LatLng position) async {
    final userLocationIcon = await _createUserLocationMarkerIcon();

    setState(() {
      _nearbyMarkers = {
        Marker(
          markerId: const MarkerId('user_location'),
          position: position,
          icon: userLocationIcon,
          anchor: const Offset(0.5, 1.0),
          infoWindow: const InfoWindow(
            title: 'Your Location',
          ),
        ),
      };
    });

    print('✅ User location marker created at ${position.latitude}, ${position.longitude}');
  }

  // ✅ NEW: Add illness markers (keeps existing user marker)
  Future<void> _addIllnessMarkers() async {
    if (_nearbyIllnessData.isEmpty) {
      print('ℹ️ No illness data to add markers for');
      return;
    }

    // ✅ Start with existing markers (user location pin)
    final markers = Set<Marker>.from(_nearbyMarkers);

    final Map<String, List<IllnessMapPoint>> locationGroups = {};

    for (final point in _nearbyIllnessData) {
      final key = '${point.latitude.toStringAsFixed(4)}_${point.longitude.toStringAsFixed(4)}';
      locationGroups.putIfAbsent(key, () => []);
      locationGroups[key]!.add(point);
    }

    for (final entry in locationGroups.entries) {
      final points = entry.value;
      final firstPoint = points.first;
      final totalCases = points.fold(0, (sum, p) => sum + p.caseCount);
      final category = points.first.category;

      final bubbleIcon = await _createCustomBubbleMarker(category, totalCases);

      markers.add(
        Marker(
          markerId: MarkerId(entry.key),
          position: LatLng(firstPoint.latitude, firstPoint.longitude),
          icon: bubbleIcon,
          anchor: const Offset(0.5, 0.5),
          infoWindow: InfoWindow(
            title: '$totalCases case${totalCases > 1 ? 's' : ''}',
            snippet: category.toUpperCase(),
          ),
        ),
      );
    }

    print('✅ Added ${markers.length - 1} illness bubble markers (total: ${markers.length} including user pin)');

    setState(() {
      _nearbyMarkers = markers;
    });
  }

  Future<BitmapDescriptor> _createCustomBubbleMarker(String category, int caseCount) async {
    double size = 70.0;
    if (caseCount >= 10) {
      size = 100.0;
    } else if (caseCount >= 5) {
      size = 85.0;
    } else if (caseCount >= 3) {
      size = 75.0;
    }

    final color = _getCategoryColor(category);

    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder);
    final paint = Paint()..isAntiAlias = true;

    paint.color = color.withOpacity(0.2);
    canvas.drawCircle(Offset(size/2 + 3, size/2 + 3), size/2 + 6, paint);

    paint.color = color.withOpacity(0.7);
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

  // ✅ RENAMED: Was _createUserLocationMarker(), now just creates icon
  Future<BitmapDescriptor> _createUserLocationMarkerIcon() async {
    const double size = 120.0;

    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder);
    final paint = Paint()..isAntiAlias = true;

    paint.color = Colors.black.withOpacity(0.3);
    canvas.drawCircle(Offset(size/2 + 3, size/2 + 5), size * 0.25, paint);

    final centerX = size / 2;
    final centerY = size * 0.25;
    final radius = size * 0.22;

    final path = Path();
    path.addOval(Rect.fromCircle(center: Offset(centerX, centerY), radius: radius));
    path.moveTo(centerX, centerY + radius);
    path.lineTo(centerX - radius * 0.5, centerY + radius + size * 0.3);
    path.lineTo(centerX + radius * 0.5, centerY + radius + size * 0.3);
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
    paint.strokeWidth = 3.0;
    canvas.drawPath(path, paint);

    paint.style = PaintingStyle.fill;
    paint.color = Colors.white;
    canvas.drawCircle(Offset(centerX, centerY), radius * 0.4, paint);

    paint.color = const Color(0xFFFF0000);
    canvas.drawCircle(Offset(centerX, centerY), radius * 0.2, paint);

    final picture = recorder.endRecording();
    final image = await picture.toImage(size.toInt(), (size * 1.1).toInt());
    final bytes = await image.toByteData(format: ui.ImageByteFormat.png);

    return BitmapDescriptor.fromBytes(bytes!.buffer.asUint8List());
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

  Widget _buildNearbyIllnessMap() {
    final appState = Provider.of<AppState>(context);
    final position = appState.currentPosition;

    // ✅ FULLSCREEN MODE
    if (_isMapFullscreen) {
      return Scaffold(
        body: Stack(
          children: [
            GoogleMap(
              initialCameraPosition: CameraPosition(
                target: position ?? const LatLng(41.8781, -87.6298),
                zoom: 14,
              ),
              markers: _nearbyMarkers,
              myLocationEnabled: false,
              myLocationButtonEnabled: false,
              zoomControlsEnabled: true,
              onMapCreated: (controller) {
                _mapController = controller;
              },
            ),
            Positioned(
              top: 50,
              right: 16,
              child: GestureDetector(
                onTap: () {
                  setState(() {
                    _isMapFullscreen = false;
                  });
                },
                child: Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.2),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: const Icon(
                    Icons.close,
                    color: Color(0xFF497CCE),
                    size: 24,
                  ),
                ),
              ),
            ),
            Positioned(
              top: 50,
              left: 16,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.95),
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.1),
                      blurRadius: 8,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                child: Text(
                  'Nearby Illness Map (20 miles)',
                  style: GoogleFonts.montserrat(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: const Color(0xFF497CCE),
                  ),
                ),
              ),
            ),

            // ✅ ONLY show "All clear" in FULLSCREEN mode
            if (_nearbyIllnessData.isEmpty && !_isLoadingMapData)
              Positioned(
                bottom: 60,
                left: 16,
                right: 16,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                  decoration: BoxDecoration(
                    color: Colors.green.withOpacity(0.95),
                    borderRadius: BorderRadius.circular(20),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.2),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.check_circle, color: Colors.white, size: 24),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          '✨ All clear! No illness reports in your area.',
                          style: GoogleFonts.montserrat(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                            color: Colors.white,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
      );
    }

    // Permission denied
    if (_permissionDenied) {
      return Container(
        margin: const EdgeInsets.symmetric(horizontal: 4),
        height: 260,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: Colors.grey),
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(20),
          child: Center(
            child: Text(
              'Location permission is required.',
              style: GoogleFonts.montserrat(),
              textAlign: TextAlign.center,
            ),
          ),
        ),
      );
    }

    // ✅ Loading state - ONLY check loading and position, NOT markers
    if (_isLoadingMapData || position == null) {
      return Container(
        margin: const EdgeInsets.symmetric(horizontal: 4),
        height: 260,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: Colors.grey),
          color: Colors.grey[50],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(20),
          child: Center(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.1),
                    blurRadius: 12,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const SizedBox(
                    width: 32,
                    height: 32,
                    child: CircularProgressIndicator(
                      strokeWidth: 3,
                      color: Color(0xFF497CCE),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Loading nearby illness reports...',
                    style: GoogleFonts.montserrat(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: const Color(0xFF497CCE),
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Please wait',
                    style: GoogleFonts.montserrat(
                      fontSize: 12,
                      color: Colors.grey[600],
                    ),
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    }

    // ✅ NORMAL MODE - Show map (NO green badge here)
    return GestureDetector(
      onTap: () {
        setState(() {
          _isMapFullscreen = true;
        });
      },
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 4),
        height: 260,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: Colors.grey),
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(20),
          child: Stack(
            children: [
              AbsorbPointer(
                absorbing: true,
                child: GoogleMap(
                  initialCameraPosition: CameraPosition(
                    target: position,
                    zoom: 13,
                  ),
                  markers: _nearbyMarkers,
                  zoomControlsEnabled: false,
                  myLocationButtonEnabled: false,
                  myLocationEnabled: false,
                  onMapCreated: (controller) {
                    _mapController = controller;
                  },
                ),
              ),

              // ✅ REMOVED: No "All clear" badge in normal mode

              // "Tap to expand" button
              Positioned(
                bottom: 12,
                right: 12,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: const Color(0xFF497CCE).withOpacity(0.9),
                    borderRadius: BorderRadius.circular(20),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.2),
                        blurRadius: 6,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(
                        Icons.fullscreen,
                        color: Colors.white,
                        size: 16,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        'Tap to expand',
                        style: GoogleFonts.montserrat(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildAnimatedLoadingCard() {
    return AnimatedBuilder(
      animation: _pulseController!,
      builder: (context, child) {
        return Container(
          padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 28),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                const Color(0xFF497CCE).withOpacity(0.05 + _pulseController!.value * 0.05),
                const Color(0xFF497CCE).withOpacity(0.10 + _pulseController!.value * 0.05),
              ],
            ),
            borderRadius: BorderRadius.circular(30),
            border: Border.all(
              color: const Color(0xFF497CCE).withOpacity(0.2 + _pulseController!.value * 0.1),
              width: 2,
            ),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF497CCE).withOpacity(0.1),
                blurRadius: 20,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Column(
            children: [
              Stack(
                alignment: Alignment.center,
                children: [
                  Container(
                    width: 80 + (_pulseController!.value * 10),
                    height: 80 + (_pulseController!.value * 10),
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: const Color(0xFF497CCE).withOpacity(0.1 - _pulseController!.value * 0.05),
                    ),
                  ),
                  Container(
                    width: 60,
                    height: 60,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: const Color(0xFF497CCE).withOpacity(0.2),
                    ),
                  ),
                  Icon(
                    Icons.health_and_safety,
                    size: 36,
                    color: const Color(0xFF497CCE).withOpacity(0.8 + _pulseController!.value * 0.2),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              Text(
                _loadingStep.isNotEmpty ? _loadingStep : 'Scanning for illness reports...',
                style: GoogleFonts.montserrat(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: const Color(0xFF497CCE),
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              Column(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(10),
                    child: LinearProgressIndicator(
                      value: _loadingProgress > 0 ? _loadingProgress / 100 : null,
                      backgroundColor: Colors.grey[200],
                      valueColor: AlwaysStoppedAnimation<Color>(
                        const Color(0xFF497CCE),
                      ),
                      minHeight: 8,
                    ),
                  ),
                  if (_loadingProgress > 0) ...[
                    const SizedBox(height: 8),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          '${_loadingProgress}%',
                          style: GoogleFonts.montserrat(
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                            color: const Color(0xFF497CCE),
                          ),
                        ),
                        Text(
                          _loadingProgress == 100 ? 'Complete!' : 'In progress...',
                          style: GoogleFonts.montserrat(
                            fontSize: 12,
                            color: Colors.grey[600],
                          ),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
              const SizedBox(height: 12),
              Text(
                'Analyzing your location and checking for nearby health alerts',
                style: GoogleFonts.montserrat(
                  fontSize: 12,
                  color: Colors.grey[600],
                ),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final appState = Provider.of<AppState>(context);

    if (_isMapFullscreen) {
      return _buildNearbyIllnessMap();
    }

    String message;
    Widget trailingIcon = const SizedBox.shrink();

    if (appState.isFetching && !appState.hasInitialData) {
      message = '';
    } else if (appState.alerts.isEmpty) {
      message = '🎉 Great news! No illness reports in your area today.';
    } else {
      final count = appState.alerts.length;
      message = '⚠️ ${count} illness report${count == 1 ? '' : 's'} detected nearby. Tap the bell to see details.';
    }

    return Scaffold(
      backgroundColor: Colors.grey[200],
      body: SafeArea(
        child: SingleChildScrollView(
          child: Column(
            children: [
              Container(
                color: const Color(0xFF497CCE),
                padding: const EdgeInsets.only(top: 4, bottom: 4),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Row(
                    children: [
                      GestureDetector(
                        onTap: () {
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => const AlertsPage(),
                            ),
                          );
                        },
                        child: Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.2),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Stack(
                            children: [
                              const Icon(Icons.notifications_none, color: Colors.white, size: 24),
                              if (appState.alerts.isNotEmpty)
                                Positioned(
                                  right: 0,
                                  top: 0,
                                  child: Container(
                                    padding: const EdgeInsets.all(2),
                                    decoration: BoxDecoration(
                                      color: Colors.red,
                                      borderRadius: BorderRadius.circular(10),
                                    ),
                                    constraints: const BoxConstraints(
                                      minWidth: 16,
                                      minHeight: 16,
                                    ),
                                    child: Text(
                                      '${appState.alerts.length}',
                                      style: GoogleFonts.montserrat(
                                        color: Colors.white,
                                        fontSize: 10,
                                        fontWeight: FontWeight.bold,
                                      ),
                                      textAlign: TextAlign.center,
                                    ),
                                  ),
                                ),
                            ],
                          ),
                        ),
                      ),
                      Expanded(
                        child: Center(
                          child: SizedBox(
                            height: 90,
                            child: Image.asset(
                              'assets/images/logo2.png',
                              height: 20,
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
              ),

              const SizedBox(height: 30),

              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: Column(
                  children: [
                    Text(
                      'Welcome to EarlySignal!',
                      style: GoogleFonts.montserrat(
                        fontSize: 26,
                        fontWeight: FontWeight.bold,
                        color: Colors.black87,
                      ),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 20),
                    Text(
                      'Democratizing public health through real-time community alerts',
                      style: GoogleFonts.montserrat(fontSize: 16),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 30),

                    if (appState.isFetching && !appState.hasInitialData)
                      _buildAnimatedLoadingCard()
                    else
                      Container(
                        padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 24),
                        decoration: BoxDecoration(
                          color: appState.alerts.isNotEmpty
                              ? Colors.orange.withOpacity(0.1)
                              : Colors.white,
                          borderRadius: BorderRadius.circular(30),
                          border: appState.alerts.isNotEmpty
                              ? Border.all(color: Colors.orange.withOpacity(0.3), width: 2)
                              : null,
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Flexible(
                              child: Text(
                                message,
                                style: GoogleFonts.montserrat(
                                  fontWeight: appState.alerts.isNotEmpty
                                      ? FontWeight.w600
                                      : FontWeight.normal,
                                  color: appState.alerts.isNotEmpty
                                      ? Colors.orange[800]
                                      : Colors.black87,
                                ),
                                textAlign: TextAlign.center,
                              ),
                            ),
                            trailingIcon,
                          ],
                        ),
                      ),

                    if (!appState.isFetching && appState.hasInitialData) ...[
                      const SizedBox(height: 16),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          GestureDetector(
                            onTap: _isRefreshing ? null : _refreshAlerts,
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                              decoration: BoxDecoration(
                                color: const Color(0xFF497CCE).withOpacity(0.1),
                                borderRadius: BorderRadius.circular(20),
                                border: Border.all(
                                  color: const Color(0xFF497CCE).withOpacity(0.3),
                                ),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  if (_isRefreshing) ...[
                                    SizedBox(
                                      width: 14,
                                      height: 14,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                        value: _loadingProgress > 0 ? _loadingProgress / 100 : null,
                                        color: const Color(0xFF497CCE),
                                      ),
                                    ),
                                  ] else ...[
                                    Icon(
                                      Icons.refresh,
                                      size: 16,
                                      color: const Color(0xFF497CCE),
                                    ),
                                  ],
                                  const SizedBox(width: 6),
                                  Text(
                                    _isRefreshing ? 'Refreshing...' : 'Check for updates',
                                    style: GoogleFonts.montserrat(
                                      fontSize: 12,
                                      color: const Color(0xFF497CCE),
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],

                    const SizedBox(height: 40),
                    Text(
                      'Nearby Illness Map',
                      style: GoogleFonts.montserrat(
                        fontWeight: FontWeight.bold,
                        fontSize: 20,
                      ),
                    ),
                    const SizedBox(height: 20),

                    _buildNearbyIllnessMap(),

                    if (_permissionDenied)
                      Padding(
                        padding: const EdgeInsets.only(top: 16),
                        child: ElevatedButton(
                          onPressed: () async {
                            if (_permissionPermanentlyDenied) {
                              await Geolocator.openAppSettings();
                            } else {
                              _determinePosition();
                            }
                          },
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF497CCE),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(30),
                            ),
                          ),
                          child: Text(
                            'Allow Location',
                            style: GoogleFonts.montserrat(color: Colors.white),
                          ),
                        ),
                      ),
                    const SizedBox(height: 40),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
      bottomNavigationBar: Container(
        padding: const EdgeInsets.symmetric(vertical: 20),
        color: const Color(0xFF497CCE),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            GestureDetector(
              onTap: () {},
              child: const Icon(Icons.home, color: Colors.white, size: 30),
            ),
            GestureDetector(
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => GenerateReportScreen()),
                );
              },
              child: const Icon(Icons.add_circle_outline, color: Colors.white, size: 30),
            ),
            GestureDetector(
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const OutbreakDashboardPage()),
                );
              },
              child: const Icon(Icons.bar_chart, color: Colors.white, size: 30),
            ),
          ],
        ),
      ),
    );
  }
}