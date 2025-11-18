import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import '../services/app_state.dart';
import '../services/illness_map_service.dart';
import '../models/illness_map_data.dart';
import 'home_screen.dart';
import 'pie_chart_page.dart';
import 'current_illness_map_page.dart';
import 'exposure_illness_map_page.dart';

class OutbreakDashboardPage extends StatefulWidget {
  const OutbreakDashboardPage({Key? key}) : super(key: key);

  @override
  State<OutbreakDashboardPage> createState() => _OutbreakDashboardPageState();
}

class _OutbreakDashboardPageState extends State<OutbreakDashboardPage> with TickerProviderStateMixin {
  int _totalActiveReports = 0;
  bool _isLoadingStats = true;
  bool _hasLocationPermission = false;
  String? _locationError;
  AnimationController? _refreshController;

  @override
  void initState() {
    super.initState();
    _refreshController = AnimationController(
      duration: const Duration(milliseconds: 1000),
      vsync: this,
    );
    _loadDashboardStats();
  }

  @override
  void dispose() {
    _refreshController?.dispose();
    super.dispose();
  }

  // ✨ Better responsive sizing that works on all devices
  double _getScaledSize(BuildContext context, double baseSize) {
    final screenWidth = MediaQuery.of(context).size.width;
    final scale = (screenWidth / 375).clamp(0.8, 1.2); // Base on iPhone SE to iPhone Pro Max
    return baseSize * scale;
  }

  // ✨ Enhanced dashboard statistics with location debugging
  Future<void> _loadDashboardStats() async {
    print('🚀 === DASHBOARD STATS LOADING ===');

    setState(() {
      _isLoadingStats = true;
      _locationError = null;
    });

    // Start refresh animation
    _refreshController?.reset();
    _refreshController?.forward();

    try {
      final appState = Provider.of<AppState>(context, listen: false);
      final position = appState.currentPosition;

      print('📍 User position from AppState: ${position?.latitude}, ${position?.longitude}');

      if (position == null) {
        print('❌ Position is null - checking location permission...');
        setState(() {
          _hasLocationPermission = false;
          _locationError = 'Location permission not granted or GPS disabled';
          _totalActiveReports = 0;
          _isLoadingStats = false;
        });
        return;
      }

      print('✅ Location available: ${position.latitude}, ${position.longitude}');
      setState(() {
        _hasLocationPermission = true;
      });

      // ✨ Load illness data with detailed logging
      print('📞 Calling getCurrentIllnessMapData...');
      final currentData = await IllnessMapService.getCurrentIllnessMapData(
        userLatitude: position.latitude,
        userLongitude: position.longitude,
      );

      print('📞 Calling getExposureIllnessMapData...');
      final exposureData = await IllnessMapService.getExposureIllnessMapData(
        userLatitude: position.latitude,
        userLongitude: position.longitude,
      );

      print('📊 Raw current data points: ${currentData?.length ?? 0}');
      print('📊 Raw exposure data points: ${exposureData?.length ?? 0}');

      if (currentData != null) {
        for (int i = 0; i < currentData.length; i++) {
          print('   Current[$i]: ${currentData[i].category} - ${currentData[i].caseCount} cases');
        }
      }

      if (exposureData != null) {
        for (int i = 0; i < exposureData.length; i++) {
          print('   Exposure[$i]: ${exposureData[i].category} - ${exposureData[i].caseCount} cases');
        }
      }

      // ✨ Calculate total active reports
      final currentCount = currentData?.fold(0, (sum, point) => sum + point.caseCount) ?? 0;
      final exposureCount = exposureData?.fold(0, (sum, point) => sum + point.caseCount) ?? 0;
      final totalCount = currentCount + exposureCount;

      print('🔢 Current illness cases: $currentCount');
      print('🔢 Exposure illness cases: $exposureCount');
      print('🔢 TOTAL ACTIVE REPORTS: $totalCount');

      setState(() {
        _totalActiveReports = totalCount;
        _isLoadingStats = false;
      });

      // Show success message
      if (totalCount > 0) {
        _showSnackBar('✅ Loaded $totalCount active reports', Colors.green);
      } else {
        _showSnackBar('ℹ️ No active reports in your area', Colors.orange);
      }

    } catch (e, stackTrace) {
      print('💥 CRITICAL ERROR loading dashboard stats: $e');
      print('📚 Stack trace: $stackTrace');

      setState(() {
        _totalActiveReports = 0;
        _isLoadingStats = false;
        _locationError = 'Error loading data: ${e.toString()}';
      });

      _showSnackBar('❌ Error loading data', Colors.red);
    }
  }

  void _showSnackBar(String message, Color color) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(message),
          backgroundColor: color,
          duration: const Duration(seconds: 2),
        ),
      );
    }
  }

  // ✨ Manual refresh with animation
  Future<void> _handleRefresh() async {
    print('🔄 Manual refresh triggered');
    await _loadDashboardStats();
  }

  @override
  Widget build(BuildContext context) {
    final screenWidth = MediaQuery.of(context).size.width;
    final isSmallScreen = screenWidth < 375;

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      body: SafeArea(
        child: Column(
          children: [
            // ✨ UPDATED HEADER: Logo instead of WiFi icon
            Container(
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    Color(0xFF497CCE),
                    Color(0xFF6B8DD6),
                  ],
                ),
              ),
              padding: EdgeInsets.only(
                top: _getScaledSize(context, 12.0),
                bottom: _getScaledSize(context, 20.0),
              ),
              child: Column(
                children: [
                  // ✨ NEW: Logo icon (white tinted) with proper sizing
                  SizedBox(
                    height: _getScaledSize(context, 65.0),
                    child: Image.asset(
                      'assets/images/logo2.png',
                      height: _getScaledSize(context, 65.0),
                      color: Colors.white, // Tints the logo white
                      colorBlendMode: BlendMode.srcIn,
                    ),
                  ),
                  SizedBox(height: _getScaledSize(context, 2.0)),

                  // ✨ Main row with proper proportions
                  Padding(
                    padding: EdgeInsets.symmetric(
                      horizontal: _getScaledSize(context, 18.0),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        // ✨ Bell icon
                        Container(
                          padding: EdgeInsets.all(_getScaledSize(context, 8.0)),
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.2),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Icon(
                            Icons.notifications_none,
                            color: Colors.white,
                            size: _getScaledSize(context, 20.0),
                          ),
                        ),

                        // ✨ Center content with proper text scaling
                        Expanded(
                          child: Column(
                            children: [
                              Text(
                                'Outbreak Dashboard',
                                style: GoogleFonts.montserrat(
                                  color: Colors.white,
                                  fontSize: _getScaledSize(context, 20.0),
                                  fontWeight: FontWeight.w700,
                                  letterSpacing: -0.3,
                                  height: 1.1,
                                ),
                                textAlign: TextAlign.center,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                              SizedBox(height: _getScaledSize(context, 2.0)),
                              Text(
                                'Real-time illness tracking & analysis',
                                style: GoogleFonts.montserrat(
                                  color: Colors.white.withOpacity(0.9),
                                  fontSize: _getScaledSize(context, 11.0),
                                  fontWeight: FontWeight.w500,
                                  height: 1.2,
                                ),
                                textAlign: TextAlign.center,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                          ),
                        ),

                        // ✨ Profile icon
                        Container(
                          padding: EdgeInsets.all(_getScaledSize(context, 8.0)),
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.2),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Icon(
                            Icons.account_circle,
                            color: Colors.white,
                            size: _getScaledSize(context, 20.0),
                          ),
                        ),
                      ],
                    ),
                  ),

                  SizedBox(height: _getScaledSize(context, 10.0)),

                  // ✨ Status indicator
                  Container(
                    padding: EdgeInsets.symmetric(
                      horizontal: _getScaledSize(context, 10.0),
                      vertical: _getScaledSize(context, 4.0),
                    ),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          width: _getScaledSize(context, 5.0),
                          height: _getScaledSize(context, 5.0),
                          decoration: BoxDecoration(
                            color: _hasLocationPermission ? const Color(0xFF10B981) : Colors.orange,
                            shape: BoxShape.circle,
                          ),
                        ),
                        SizedBox(width: _getScaledSize(context, 5.0)),
                        Text(
                          _hasLocationPermission ? 'System Active' : 'Location Issue',
                          style: GoogleFonts.montserrat(
                            color: Colors.white,
                            fontSize: _getScaledSize(context, 9.0),
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),

            // ✨ Main content with better proportions
            Expanded(
              child: RefreshIndicator(
                onRefresh: _handleRefresh,
                color: const Color(0xFF497CCE),
                child: SingleChildScrollView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: EdgeInsets.all(_getScaledSize(context, 16.0)),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // ✨ Active reports card with better proportions
                      GestureDetector(
                        onTap: _handleRefresh,
                        child: Container(
                          width: double.infinity,
                          padding: EdgeInsets.all(_getScaledSize(context, 18.0)),
                          decoration: BoxDecoration(
                            gradient: const LinearGradient(
                              colors: [Color(0xFF667EEA), Color(0xFF764BA2)],
                            ),
                            borderRadius: BorderRadius.circular(14),
                            boxShadow: [
                              BoxShadow(
                                color: const Color(0xFF667EEA).withOpacity(0.3),
                                blurRadius: 12,
                                offset: const Offset(0, 4),
                              ),
                            ],
                          ),
                          child: Column(
                            children: [
                              Row(
                                children: [
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          'Active Reports',
                                          style: GoogleFonts.montserrat(
                                            color: Colors.white,
                                            fontSize: _getScaledSize(context, 10.0),
                                            fontWeight: FontWeight.w600,
                                          ),
                                        ),
                                        SizedBox(height: _getScaledSize(context, 3.0)),
                                        _isLoadingStats
                                            ? SizedBox(
                                          width: 18,
                                          height: 18,
                                          child: CircularProgressIndicator(
                                            color: Colors.white,
                                            strokeWidth: 1.5,
                                          ),
                                        )
                                            : Text(
                                          _totalActiveReports.toString(),
                                          style: GoogleFonts.montserrat(
                                            color: Colors.white,
                                            fontSize: isSmallScreen ?
                                            _getScaledSize(context, 22.0) :
                                            _getScaledSize(context, 24.0),
                                            fontWeight: FontWeight.w800,
                                            letterSpacing: -0.5,
                                            height: 1.1,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                  // ✨ Refresh icon with proper sizing
                                  _refreshController != null
                                      ? AnimatedBuilder(
                                    animation: _refreshController!,
                                    builder: (context, child) {
                                      return Transform.rotate(
                                        angle: _refreshController!.value * 2 * 3.14159,
                                        child: Container(
                                          padding: EdgeInsets.all(_getScaledSize(context, 10.0)),
                                          decoration: BoxDecoration(
                                            color: Colors.white.withOpacity(0.2),
                                            borderRadius: BorderRadius.circular(10),
                                          ),
                                          child: Icon(
                                            Icons.refresh,
                                            color: Colors.white,
                                            size: _getScaledSize(context, 18.0),
                                          ),
                                        ),
                                      );
                                    },
                                  )
                                      : Container(
                                    padding: EdgeInsets.all(_getScaledSize(context, 10.0)),
                                    decoration: BoxDecoration(
                                      color: Colors.white.withOpacity(0.2),
                                      borderRadius: BorderRadius.circular(10),
                                    ),
                                    child: Icon(
                                      Icons.refresh,
                                      color: Colors.white,
                                      size: _getScaledSize(context, 18.0),
                                    ),
                                  ),
                                ],
                              ),

                              SizedBox(height: _getScaledSize(context, 10.0)),

                              // ✨ Status info
                              Container(
                                padding: EdgeInsets.all(_getScaledSize(context, 8.0)),
                                decoration: BoxDecoration(
                                  color: Colors.white.withOpacity(0.1),
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: Row(
                                  children: [
                                    Icon(
                                      _locationError != null
                                          ? Icons.error_outline
                                          : Icons.touch_app,
                                      color: Colors.white,
                                      size: _getScaledSize(context, 13.0),
                                    ),
                                    SizedBox(width: _getScaledSize(context, 6.0)),
                                    Expanded(
                                      child: Text(
                                        _locationError ?? 'Tap to refresh data',
                                        style: GoogleFonts.montserrat(
                                          color: Colors.white.withOpacity(0.9),
                                          fontSize: _getScaledSize(context, 9.5),
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),

                      SizedBox(height: _getScaledSize(context, 22.0)),

                      // ✨ Section header with proper sizing
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Explore Data',
                                style: GoogleFonts.montserrat(
                                  fontSize: _getScaledSize(context, 17.0),
                                  fontWeight: FontWeight.w700,
                                  color: const Color(0xFF1F2937),
                                  letterSpacing: -0.2,
                                ),
                              ),
                              Text(
                                'Analyze illness patterns and trends',
                                style: GoogleFonts.montserrat(
                                  fontSize: _getScaledSize(context, 11.0),
                                  color: Colors.grey[600],
                                ),
                              ),
                            ],
                          ),
                          // ✅ Manual refresh button
                          GestureDetector(
                            onTap: _handleRefresh,
                            child: Container(
                              padding: EdgeInsets.all(_getScaledSize(context, 8.0)),
                              decoration: BoxDecoration(
                                color: const Color(0xFF497CCE).withOpacity(0.1),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: _refreshController != null
                                  ? AnimatedBuilder(
                                animation: _refreshController!,
                                builder: (context, child) {
                                  return Transform.rotate(
                                    angle: _refreshController!.value * 2 * 3.14159,
                                    child: Icon(
                                      Icons.refresh,
                                      color: const Color(0xFF497CCE),
                                      size: _getScaledSize(context, 16.0),
                                    ),
                                  );
                                },
                              )
                                  : Icon(
                                Icons.refresh,
                                color: const Color(0xFF497CCE),
                                size: _getScaledSize(context, 16.0),
                              ),
                            ),
                          ),
                        ],
                      ),
                      SizedBox(height: _getScaledSize(context, 18.0)),

                      // ✨ Navigation cards with better proportions
                      _modernNavCard(
                        context,
                        title: 'Illness Breakdown',
                        subtitle: 'Explore distribution of illness types',
                        icon: Icons.pie_chart,
                        gradient: const LinearGradient(
                          colors: [Color(0xFF4F46E5), Color(0xFF7C3AED)],
                        ),
                        destination: const PieChartPage(),
                      ),

                      SizedBox(height: _getScaledSize(context, 14.0)),

                      _modernNavCard(
                        context,
                        title: 'Nearby Reports',
                        subtitle: 'Current illness reports around you',
                        icon: Icons.people_outline,
                        gradient: const LinearGradient(
                          colors: [Color(0xFF059669), Color(0xFF0D9488)],
                        ),
                        destination: const CurrentIllnessMapPage(),
                      ),

                      SizedBox(height: _getScaledSize(context, 14.0)),

                      _modernNavCard(
                        context,
                        title: 'Exposure Sources',
                        subtitle: 'Track where illnesses originated',
                        icon: Icons.location_on,
                        gradient: const LinearGradient(
                          colors: [Color(0xFFDC2626), Color(0xFFEA580C)],
                        ),
                        destination: const ExposureIllnessMapPage(),
                      ),

                      SizedBox(height: _getScaledSize(context, 28.0)),

                      // ✨ Additional info section
                      Container(
                        padding: EdgeInsets.all(_getScaledSize(context, 16.0)),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(14),
                          border: Border.all(color: Colors.grey[200]!),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Container(
                                  padding: EdgeInsets.all(_getScaledSize(context, 6.0)),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFF3B82F6).withOpacity(0.1),
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: Icon(
                                    Icons.info_outline,
                                    color: const Color(0xFF3B82F6),
                                    size: _getScaledSize(context, 16.0),
                                  ),
                                ),
                                SizedBox(width: _getScaledSize(context, 10.0)),
                                Text(
                                  'Data Updated',
                                  style: GoogleFonts.montserrat(
                                    fontSize: _getScaledSize(context, 14.0),
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ],
                            ),
                            SizedBox(height: _getScaledSize(context, 6.0)),
                            Text(
                              'Last updated 5 minutes ago • Real-time monitoring active',
                              style: GoogleFonts.montserrat(
                                fontSize: _getScaledSize(context, 11.0),
                                color: Colors.grey[600],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),

      // ✨ Bottom navigation with proper sizing
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFF497CCE), Color(0xFF6B8DD6)],
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black12,
              blurRadius: 10,
              offset: Offset(0, -2),
            ),
          ],
        ),
        padding: EdgeInsets.symmetric(vertical: _getScaledSize(context, 14.0)),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            _navButton(
              icon: Icons.home,
              onTap: () => Navigator.pushNamedAndRemoveUntil(
                  context, '/home', (route) => false),
            ),
            _navButton(
              icon: Icons.add_circle_outline,
              onTap: () => Navigator.pushNamed(context, '/generate-report'),
            ),
            _navButton(
              icon: Icons.bar_chart,
              isActive: true,
              onTap: () {},
            ),
          ],
        ),
      ),
    );
  }

  Widget _modernNavCard(
      BuildContext context, {
        required String title,
        required String subtitle,
        required IconData icon,
        required Gradient gradient,
        required Widget destination,
      }) {
    return GestureDetector(
      onTap: () => Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => destination),
      ),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(14),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.08),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(14),
          child: Stack(
            children: [
              // ✨ Gradient accent bar
              Positioned(
                left: 0,
                top: 0,
                bottom: 0,
                width: 4,
                child: Container(
                  decoration: BoxDecoration(gradient: gradient),
                ),
              ),

              Padding(
                padding: EdgeInsets.all(_getScaledSize(context, 16.0)),
                child: Row(
                  children: [
                    // ✨ Icon with proper sizing
                    Container(
                      width: _getScaledSize(context, 46.0),
                      height: _getScaledSize(context, 46.0),
                      decoration: BoxDecoration(
                        gradient: gradient,
                        borderRadius: BorderRadius.circular(10),
                        boxShadow: [
                          BoxShadow(
                            color: gradient.colors.first.withOpacity(0.3),
                            blurRadius: 8,
                            offset: const Offset(0, 4),
                          ),
                        ],
                      ),
                      child: Icon(
                        icon,
                        color: Colors.white,
                        size: _getScaledSize(context, 22.0),
                      ),
                    ),

                    SizedBox(width: _getScaledSize(context, 14.0)),

                    // ✨ Content with proper text sizing
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            title,
                            style: GoogleFonts.montserrat(
                              fontSize: _getScaledSize(context, 15.0),
                              fontWeight: FontWeight.w700,
                              color: const Color(0xFF1F2937),
                              letterSpacing: -0.2,
                              height: 1.2,
                            ),
                          ),
                          SizedBox(height: _getScaledSize(context, 2.0)),
                          Text(
                            subtitle,
                            style: GoogleFonts.montserrat(
                              fontSize: _getScaledSize(context, 11.0),
                              color: Colors.grey[600],
                              height: 1.3,
                            ),
                          ),
                        ],
                      ),
                    ),

                    // ✨ Arrow indicator
                    Container(
                      padding: EdgeInsets.all(_getScaledSize(context, 6.0)),
                      decoration: BoxDecoration(
                        color: Colors.grey[100],
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Icon(
                        Icons.arrow_forward_ios,
                        size: _getScaledSize(context, 12.0),
                        color: Colors.grey[600],
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _navButton({
    required IconData icon,
    required VoidCallback onTap,
    bool isActive = false,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: EdgeInsets.all(_getScaledSize(context, 10.0)),
        decoration: BoxDecoration(
          color: isActive
              ? Colors.white.withOpacity(0.2)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Icon(
          icon,
          color: Colors.white,
          size: _getScaledSize(context, 24.0),
        ),
      ),
    );
  }
}