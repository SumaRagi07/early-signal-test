import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:google_fonts/google_fonts.dart';
import '../services/app_state.dart';
import '../services/illness_chart_service.dart';
import '../models/illness_data.dart';
import 'home_screen.dart';
import 'outbreak_dashboard.dart';

class PieChartPage extends StatefulWidget {
  const PieChartPage({Key? key}) : super(key: key);

  @override
  State<PieChartPage> createState() => _PieChartPageState();
}

class _PieChartPageState extends State<PieChartPage> {
  PieChartResponse? _chartData;
  bool _isLoading = true;
  String? _error;
  double _selectedRadius = 5.0;

  @override
  void initState() {
    super.initState();
    _loadChartData();
  }

  Future<void> _loadChartData() async {
    final appState = Provider.of<AppState>(context, listen: false);
    final position = appState.currentPosition;

    if (position?.latitude == null || position?.longitude == null) {
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
      final data = await IllnessChartService.getPieChartData(
        latitude: position!.latitude,
        longitude: position.longitude,
        radiusMiles: _selectedRadius,
      );

      setState(() {
        _chartData = data;
        _isLoading = false;
        if (data == null) {
          _error = 'Failed to load chart data';
        }
      });
    } catch (e) {
      setState(() {
        _error = 'Error loading data: $e';
        _isLoading = false;
      });
    }
  }

  void _onRadiusChanged(double newRadius) {
    setState(() {
      _selectedRadius = newRadius;
    });
    _loadChartData();
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey[100],
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            Expanded(
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                child: Column(
                  children: [
                    const SizedBox(height: 24),
                    _buildTitle(),
                    _buildRadiusFilter(),
                    const SizedBox(height: 16),
                    _buildChartContent(),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: _buildBottomNavigation(),
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
            // ✨ Back arrow button
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

            // ✨ Centered logo
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

            // ✨ Profile icon
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


  Widget _buildTitle() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        children: [
          Row(
            children: [
              Icon(Icons.pie_chart, color: const Color(0xFF497CCE), size: 24),
              const SizedBox(width: 8),
              Text(
                "Illness Types Breakdown",
                style: GoogleFonts.montserrat(fontSize: 20, fontWeight: FontWeight.bold),
              ),
            ],
          ),
          const SizedBox(height: 8),
          if (_chartData != null)
            Text(
              "Total Cases: ${_chartData!.totalCases} within ${_selectedRadius.toInt()} miles",
              style: GoogleFonts.montserrat(fontSize: 14, color: Colors.grey[600]),
            ),
        ],
      ),
    );
  }

  Widget _buildRadiusFilter() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        children: [
          Row(
            children: [
              Icon(Icons.tune, color: const Color(0xFF497CCE), size: 20),
              const SizedBox(width: 8),
              Text(
                "Search Radius: ",
                style: GoogleFonts.montserrat(fontWeight: FontWeight.w600, fontSize: 16),
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: const Color(0xFF497CCE).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  "${_selectedRadius.toInt()} miles",
                  style: GoogleFonts.montserrat(
                    fontWeight: FontWeight.bold,
                    color: const Color(0xFF497CCE),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          SliderTheme(
            data: SliderTheme.of(context).copyWith(
              activeTrackColor: const Color(0xFF497CCE),
              inactiveTrackColor: const Color(0xFF497CCE).withOpacity(0.2),
              thumbColor: const Color(0xFF497CCE),
              overlayColor: const Color(0xFF497CCE).withOpacity(0.1),
              thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 12),
              overlayShape: const RoundSliderOverlayShape(overlayRadius: 20),
            ),
            child: Slider(
              value: _selectedRadius,
              min: 1.0,
              max: 20.0,
              divisions: 19,
              onChanged: _onRadiusChanged,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChartContent() {
    if (_isLoading) {
      return Container(
        height: MediaQuery.of(context).size.height * 0.5,
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const CircularProgressIndicator(color: Color(0xFF497CCE)),
              const SizedBox(height: 16),
              Text(
                "Loading health data...",
                style: GoogleFonts.montserrat(fontSize: 16),
              ),
            ],
          ),
        ),
      );
    }

    if (_error != null) {
      return Container(
        height: MediaQuery.of(context).size.height * 0.5,
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.error_outline, size: 64, color: Colors.grey[400]),
              const SizedBox(height: 16),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Text(
                  _error!,
                  textAlign: TextAlign.center,
                  style: GoogleFonts.montserrat(fontSize: 16),
                ),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _loadChartData,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF497CCE),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: Text(
                  "Retry",
                  style: GoogleFonts.montserrat(color: Colors.white),
                ),
              ),
            ],
          ),
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        children: [
          _buildStatsCard(),
          const SizedBox(height: 20),
          (_chartData?.data.isEmpty ?? true)
              ? _buildNoCasesView()
              : _buildDataBasedView(),
          const SizedBox(height: 100),
        ],
      ),
    );
  }

  Widget _buildStatsCard() {
    final totalCases = _chartData?.totalCases ?? 0;
    final totalCategories = _chartData?.totalCategories ?? 0;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: totalCases > 0
              ? [
            const Color(0xFF497CCE),
            const Color(0xFF497CCE).withOpacity(0.8),
          ]
              : [
            const Color(0xFF10B981),
            const Color(0xFF10B981).withOpacity(0.8),
          ],
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: totalCases > 0
                ? const Color(0xFF497CCE).withOpacity(0.3)
                : const Color(0xFF10B981).withOpacity(0.3),
            blurRadius: 12,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          _buildStatItem("Cases", "$totalCases", Icons.medical_services, Colors.white),
          Container(width: 1, height: 40, color: Colors.white.withOpacity(0.3)),
          _buildStatItem("Types", "$totalCategories", Icons.category, Colors.white),
          Container(width: 1, height: 40, color: Colors.white.withOpacity(0.3)),
          _buildStatItem("Range", "${_selectedRadius.toInt()} mi", Icons.location_on, Colors.white),
        ],
      ),
    );
  }

  Widget _buildStatItem(String label, String value, IconData icon, Color color) {
    return Column(
      children: [
        Icon(icon, color: color, size: 28),
        const SizedBox(height: 8),
        Text(
          value,
          style: GoogleFonts.montserrat(
            fontSize: 22,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        Text(
          label,
          style: GoogleFonts.montserrat(
            fontSize: 12,
            color: color.withOpacity(0.9),
          ),
        ),
      ],
    );
  }

  Widget _buildNoCasesView() {
    return Container(
      constraints: BoxConstraints(
        minHeight: MediaQuery.of(context).size.height * 0.4,
      ),
      child: Column(
        children: [
          Row(
            children: [
              Icon(Icons.health_and_safety, color: const Color(0xFF10B981), size: 24),
              const SizedBox(width: 8),
              Text(
                "All Clear in Your Area!",
                style: GoogleFonts.montserrat(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: const Color(0xFF10B981),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),

          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(32),
            decoration: BoxDecoration(
              color: const Color(0xFF10B981).withOpacity(0.1),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: const Color(0xFF10B981).withOpacity(0.2)),
            ),
            child: Column(
              children: [
                Container(
                  width: 80,
                  height: 80,
                  decoration: BoxDecoration(
                    color: const Color(0xFF10B981),
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: const Color(0xFF10B981).withOpacity(0.3),
                        blurRadius: 20,
                        offset: const Offset(0, 8),
                      ),
                    ],
                  ),
                  child: const Icon(
                    Icons.check_circle_outline,
                    color: Colors.white,
                    size: 40,
                  ),
                ),
                const SizedBox(height: 20),
                Text(
                  "No Health Reports",
                  style: GoogleFonts.montserrat(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    color: const Color(0xFF497CCE),
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  "No illness cases reported within ${_selectedRadius.toInt()} miles of your location",
                  textAlign: TextAlign.center,
                  style: GoogleFonts.montserrat(
                    fontSize: 14,
                    color: Colors.grey[600],
                  ),
                ),
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  decoration: BoxDecoration(
                    color: const Color(0xFF10B981).withOpacity(0.1),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: const Color(0xFF10B981).withOpacity(0.3)),
                  ),
                  child: Text(
                    "Your area looks healthy! 🌟",
                    style: GoogleFonts.montserrat(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      color: const Color(0xFF497CCE),
                    ),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 20),
          _buildHealthTips(),
        ],
      ),
    );
  }

  Widget _buildHealthTips() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF497CCE).withOpacity(0.2)),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Icon(Icons.tips_and_updates, color: const Color(0xFF497CCE), size: 20),
              const SizedBox(width: 8),
              Text(
                "Stay Healthy Tips",
                style: GoogleFonts.montserrat(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: const Color(0xFF497CCE),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            "Great news! No illness reports in your area. Keep monitoring regularly and maintain healthy habits to stay safe.",
            style: GoogleFonts.montserrat(fontSize: 14, color: Colors.grey[600]),
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _buildHealthTip(Icons.local_hospital, "Stay Alert"),
              _buildHealthTip(Icons.refresh, "Check Daily"),
              _buildHealthTip(Icons.trending_up, "Expand Area"),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildHealthTip(IconData icon, String tip) {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: const Color(0xFF497CCE).withOpacity(0.1),
            shape: BoxShape.circle,
          ),
          child: Icon(icon, color: const Color(0xFF497CCE), size: 20),
        ),
        const SizedBox(height: 8),
        Text(
          tip,
          style: GoogleFonts.montserrat(
            fontSize: 12,
            color: const Color(0xFF497CCE),
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }

  Widget _buildDataBasedView() {
    final totalCases = _chartData!.totalCases;
    final categoryCount = _chartData!.totalCategories;

    return totalCases <= 3 || categoryCount == 1
        ? _buildDetailedListView()
        : _buildPieChartView();
  }

  Widget _buildDetailedListView() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(Icons.list_alt, color: const Color(0xFF497CCE), size: 24),
            const SizedBox(width: 8),
            Text(
              "Detailed Health Reports",
              style: GoogleFonts.montserrat(fontSize: 18, fontWeight: FontWeight.bold),
            ),
          ],
        ),
        const SizedBox(height: 16),

        ...(_chartData!.data.asMap().entries.map((entry) {
          final index = entry.key;
          final data = entry.value;
          final color = _getCategoryColor(data.category);

          return Container(
            margin: const EdgeInsets.only(bottom: 16),
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                  color: color.withOpacity(0.1),
                  blurRadius: 10,
                  offset: const Offset(0, 4),
                ),
              ],
              border: Border.all(color: color.withOpacity(0.2), width: 1.5),
            ),
            child: Row(
              children: [
                Container(
                  width: 60,
                  height: 60,
                  decoration: BoxDecoration(
                    color: color,
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: color.withOpacity(0.4),
                        blurRadius: 8,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: Icon(
                    _getCategoryIcon(data.category),
                    color: Colors.white,
                    size: 28,
                  ),
                ),
                const SizedBox(width: 20),

                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        data.category.toUpperCase(),
                        style: GoogleFonts.montserrat(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: Colors.grey[800],
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        "${data.caseCount} ${data.caseCount == 1 ? 'case' : 'cases'} reported",
                        style: GoogleFonts.montserrat(
                          fontSize: 14,
                          color: Colors.grey[600],
                        ),
                      ),
                      const SizedBox(height: 12),

                      Container(
                        height: 8,
                        decoration: BoxDecoration(
                          color: Colors.grey[200],
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: FractionallySizedBox(
                          alignment: Alignment.centerLeft,
                          widthFactor: data.percentage / 100,
                          child: Container(
                            decoration: BoxDecoration(
                              color: color,
                              borderRadius: BorderRadius.circular(4),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: color.withOpacity(0.3)),
                  ),
                  child: Text(
                    "${data.percentage.toStringAsFixed(0)}%",
                    style: GoogleFonts.montserrat(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: color,
                    ),
                  ),
                ),
              ],
            ),
          );
        }).toList()),

        const SizedBox(height: 20),
        _buildActionSuggestions(),
      ],
    );
  }

  Widget _buildActionSuggestions() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.orange.withOpacity(0.2)),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Icon(Icons.lightbulb_outline, color: Colors.orange[600], size: 20),
              const SizedBox(width: 8),
              Text(
                "Recommendations",
                style: GoogleFonts.montserrat(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: Colors.grey[700],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            _chartData!.totalCases <= 3
                ? "Low activity in your area. Continue monitoring by checking back regularly and consider expanding your search radius."
                : "Multiple illness types detected. Consider taking appropriate precautions and stay informed about the specific categories in your area.",
            style: GoogleFonts.montserrat(fontSize: 14, color: Colors.grey[600]),
          ),
        ],
      ),
    );
  }

  Widget _buildPieChartView() {
    return Column(
      children: [
        Row(
          children: [
            Icon(Icons.donut_small, color: const Color(0xFF497CCE), size: 24),
            const SizedBox(width: 8),
            Text(
              "Illness Distribution Chart",
              style: GoogleFonts.montserrat(fontSize: 18, fontWeight: FontWeight.bold),
            ),
          ],
        ),
        const SizedBox(height: 20),

        Container(
          height: MediaQuery.of(context).size.width * 0.8,
          constraints: const BoxConstraints(maxHeight: 300, minHeight: 250),
          child: PieChart(
            PieChartData(
              sections: _buildPieChartSections(),
              centerSpaceRadius: 50,
              sectionsSpace: 3,
              startDegreeOffset: -90,
            ),
          ),
        ),

        const SizedBox(height: 20),
        _buildEnhancedLegend(),
      ],
    );
  }

  List<PieChartSectionData> _buildPieChartSections() {
    return _chartData!.data.asMap().entries.map((entry) {
      final index = entry.key;
      final data = entry.value;
      final color = _getCategoryColor(data.category);

      return PieChartSectionData(
        color: color,
        value: data.percentage,
        title: _chartData!.totalCategories > 1 ? '${data.percentage.toStringAsFixed(0)}%' : '',
        radius: 100,
        titleStyle: GoogleFonts.montserrat(
          fontSize: 14,
          fontWeight: FontWeight.bold,
          color: Colors.white,
          shadows: [
            const Shadow(
              color: Colors.black26,
              offset: Offset(1, 1),
              blurRadius: 2,
            ),
          ],
        ),
        titlePositionPercentageOffset: 0.6,
      );
    }).toList();
  }

  Widget _buildEnhancedLegend() {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFF497CCE).withOpacity(0.1),
              borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
            ),
            child: Row(
              children: [
                Icon(Icons.legend_toggle, color: const Color(0xFF497CCE), size: 20),
                const SizedBox(width: 8),
                Text(
                  "Category Breakdown",
                  style: GoogleFonts.montserrat(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: const Color(0xFF497CCE),
                  ),
                ),
              ],
            ),
          ),

          ...(_chartData!.data.asMap().entries.map((entry) {
            final index = entry.key;
            final data = entry.value;
            final color = _getCategoryColor(data.category);
            final isLast = index == _chartData!.data.length - 1;

            return Container(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
              decoration: BoxDecoration(
                border: isLast ? null : Border(
                  bottom: BorderSide(color: Colors.grey[200]!, width: 1),
                ),
                borderRadius: isLast ? const BorderRadius.vertical(bottom: Radius.circular(16)) : null,
              ),
              child: Row(
                children: [
                  Container(
                    width: 24,
                    height: 24,
                    decoration: BoxDecoration(
                      color: color,
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: color.withOpacity(0.4),
                          blurRadius: 4,
                          offset: const Offset(0, 2),
                        ),
                      ],
                    ),
                    child: Icon(
                      _getCategoryIcon(data.category),
                      color: Colors.white,
                      size: 14,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          data.category.toUpperCase(),
                          style: GoogleFonts.montserrat(
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        Text(
                          "${data.caseCount} cases (${data.percentage.toStringAsFixed(1)}%)",
                          style: GoogleFonts.montserrat(
                            fontSize: 12,
                            color: Colors.grey[600],
                          ),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: color.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      "${data.percentage.toStringAsFixed(0)}%",
                      style: GoogleFonts.montserrat(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: color,
                      ),
                    ),
                  ),
                ],
              ),
            );
          }).toList()),
        ],
      ),
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
              MaterialPageRoute(builder: (_) => const OutbreakDashboardPage()),
            ),
            child: const Icon(Icons.bar_chart, color: Colors.white, size: 30),
          ),
        ],
      ),
    );
  }
}