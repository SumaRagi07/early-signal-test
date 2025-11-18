import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:geolocator/geolocator.dart';
import 'map_fullscreen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with WidgetsBindingObserver {
  LatLng? _currentPosition;
  bool _permissionDenied = false;
  bool _permissionPermanentlyDenied = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _determinePosition();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _determinePosition(); // Recheck location when returning from settings
    }
  }

  Future<void> _determinePosition() async {
    try {
      bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        setState(() {
          _permissionDenied = true;
          _permissionPermanentlyDenied = false;
        });
        return;
      }

      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }

      if (permission == LocationPermission.deniedForever) {
        setState(() {
          _permissionDenied = true;
          _permissionPermanentlyDenied = true;
        });
        return;
      }

      //  Permission granted
      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );

      setState(() {
        _currentPosition = LatLng(position.latitude, position.longitude);
        _permissionDenied = false;
        _permissionPermanentlyDenied = false;
      });
    } catch (e) {
      print("Error getting location: $e");
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error getting location. Please try again.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey[200],
      body: SafeArea(
        child: SingleChildScrollView(
          child: Column(
            children: [
              // Top bar
              Container(
                color: const Color(0xFF497CCE),
                padding: const EdgeInsets.only(top: 16, bottom: 16),
                child: Column(
                  children: [
                    const Icon(Icons.network_wifi, color: Colors.white, size: 28),
                    const SizedBox(height: 12),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.center,
                        children: [
                          const Icon(Icons.notifications_none, color: Colors.white, size: 28),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Container(
                              height: 40,
                              decoration: BoxDecoration(
                                color: Colors.white,
                                borderRadius: BorderRadius.circular(30),
                              ),
                              padding: const EdgeInsets.symmetric(horizontal: 16),
                              child: Row(
                                children: const [
                                  Expanded(
                                    child: TextField(
                                      decoration: InputDecoration(
                                        hintText: 'Search...',
                                        border: InputBorder.none,
                                        isCollapsed: true,
                                        contentPadding: EdgeInsets.symmetric(vertical: 8),
                                      ),
                                      style: TextStyle(fontSize: 15),
                                    ),
                                  ),
                                  Icon(Icons.search, color: Colors.grey),
                                ],
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          const Icon(Icons.account_circle, color: Colors.white, size: 28),
                        ],
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 30),
              Text(
                'Welcome to EarlySignal!',
                style: GoogleFonts.montserrat(
                  fontSize: 30,
                  fontWeight: FontWeight.bold,
                  color: Colors.black87,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 20),
              Text(
                'Democratizing public health and\naccelerating grassroots outbreak\nresponse with AI',
                style: GoogleFonts.montserrat(fontSize: 20),
                textAlign: TextAlign.center,
              ),

              const SizedBox(height: 30),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 30),
                child: Container(
                  padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 70),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(30),
                  ),
                  child: Text(
                    'You currently have no alerts!',
                    style: GoogleFonts.montserrat(),
                    textAlign: TextAlign.center,
                  ),
                ),
              ),

              const SizedBox(height: 40),
              Text(
                'Outbreak Map',
                style: GoogleFonts.montserrat(
                  fontWeight: FontWeight.bold,
                  fontSize: 20,
                ),
              ),

              const SizedBox(height: 20),
              GestureDetector(
                onTap: _permissionDenied
                    ? null
                    : () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const MapFullScreen()),
                  );
                },
                child: Container(
                  margin: const EdgeInsets.symmetric(horizontal: 20),
                  height: 260,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: Colors.grey),
                  ),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(20),
                    child: AbsorbPointer(
                      child: _permissionDenied
                          ? Center(
                        child: Text(
                          'Location permission is required.',
                          style: GoogleFonts.montserrat(),
                          textAlign: TextAlign.center,
                        ),
                      )
                          : _currentPosition == null
                          ? const Center(child: CircularProgressIndicator())
                          : GoogleMap(
                        initialCameraPosition: CameraPosition(
                          target: _currentPosition!,
                          zoom: 11,
                        ),
                        zoomControlsEnabled: false,
                        myLocationButtonEnabled: false,
                        myLocationEnabled: false,
                        onMapCreated: (controller) {},
                      ),
                    ),
                  ),
                ),
              ),

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
      ),
      bottomNavigationBar: Container(
        padding: const EdgeInsets.symmetric(vertical: 20),
        color: const Color(0xFF497CCE),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: const [
            Icon(Icons.home, color: Colors.white, size: 30),
            Icon(Icons.add_circle_outline, color: Colors.white, size: 30),
            Icon(Icons.bar_chart, color: Colors.white, size: 30),
          ],
        ),
      ),
    );
  }
}