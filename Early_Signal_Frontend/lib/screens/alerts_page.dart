import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../models/alert_item.dart';
import '../services/app_state.dart';

class AlertsPage extends StatelessWidget {
  const AlertsPage({super.key});

  // ✅ UPDATED: Category-based personalized messages using new AlertItem properties
  String getCleanMessage(AlertItem alert) {
    final category = alert.category.toLowerCase();
    final disease = alert.disease;
    final size = alert.clusterSize;
    final location = alert.isLocalToUser ? 'in your neighborhood' : 'nearby';

    final venueName = alert.venueNameOnly;
    final fullLocation = alert.venueName;

    switch (category) {
      case 'airborne':
        return '😷 $size people $location reported $disease.\n\n'
            '⚠️ Spreads through air when people breathe, cough, or sneeze.\n\n'
            '💡 Stay Safe:\n'
            '• Wear a mask in crowded spaces\n'
            '• Keep 6 feet distance\n'
            '• Ensure good ventilation\n'
            '• Monitor symptoms and stay home if unwell';

      case 'foodborne':
        return '🍔 $size people $location reported $disease after visiting $fullLocation.\n\n'
            '⚠️ Possible food contamination at this location.\n\n'
            '💡 Stay Safe:\n'
            '• Consider avoiding $venueName for a few days\n'
            '• If you ate there recently, watch for nausea, vomiting, or stomach cramps\n'
            '• Seek medical help if symptoms worsen';

      case 'waterborne':
        return '🚱 $size people $location reported $disease near $fullLocation.\n\n'
            '⚠️ Possible water contamination in this area.\n\n'
            '💡 Stay Safe:\n'
            '• Use bottled or boiled water for a few days\n'
            '• Avoid ice and fountain drinks\n'
            '• Wash hands with safe water';

      case 'insect-borne':
      case 'insect_borne':
        return '🦟 $size people $location reported $disease near $fullLocation.\n\n'
            '⚠️ High mosquito/tick activity in this area.\n\n'
            '💡 Stay Safe:\n'
            '• Avoid $venueName during dawn/dusk for a few days\n'
            '• Use insect repellent with DEET (20-30%)\n'
            '• Wear long sleeves and pants\n'
            '• Check for ticks after outdoor activities';

      case 'direct contact':
      case 'direct_contact':
        return '👥 $size people $location reported $disease at $fullLocation.\n\n'
            '⚠️ Spreads through person-to-person contact.\n\n'
            '💡 Stay Safe:\n'
            '• Consider avoiding $venueName for a few days\n'
            '• Wash hands frequently (20 seconds with soap)\n'
            '• Avoid touching your face\n'
            '• Monitor for symptoms like rash or fever';

      default:
        final locationText = fullLocation.isNotEmpty ? fullLocation : 'your area';
        return '📢 $size people $location reported $disease near $locationText.\n\n'
            '💡 Stay Safe:\n'
            '• Maintain good hygiene\n'
            '• Monitor your health\n'
            '• Avoid crowded places for a few days';
    }
  }

  // ✅ Color based on local vs major outbreak
  Color getAlertSeverity(AlertItem alert) {
    if (alert.isLocalToUser) {
      return const Color(0xFF497CCE); // Blue for local
    } else {
      return Colors.orange; // Orange for major outbreaks
    }
  }

  @override
  Widget build(BuildContext context) {
    final appState = Provider.of<AppState>(context);
    final alerts = appState.alerts;

    return Scaffold(
      backgroundColor: Colors.grey[200],
      body: SafeArea(
        child: Column(
          children: [
            // ✨ HEADER
            Container(
              color: const Color(0xFF497CCE),
              padding: const EdgeInsets.only(top: 8, bottom: 8),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Row(
                  children: [
                    // Back button
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

                    // Centered logo
                    Expanded(
                      child: Center(
                        child: SizedBox(
                          height: 85,
                          child: Image.asset(
                            'assets/images/logo2.png',
                            height: 50,
                            color: Colors.white,
                            colorBlendMode: BlendMode.srcIn,
                          ),
                        ),
                      ),
                    ),

                    // Profile icon
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

            // Alert List
            Expanded(
              child: alerts.isEmpty
                  ? Center(
                child: Padding(
                  padding: const EdgeInsets.all(32.0),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.check_circle_outline,
                        size: 80,
                        color: Colors.green[400],
                      ),
                      const SizedBox(height: 16),
                      Text(
                        '🎉 All Clear!',
                        style: GoogleFonts.montserrat(
                          fontSize: 24,
                          fontWeight: FontWeight.bold,
                          color: Colors.green[700],
                        ),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'No illness reports in your area right now.',
                        style: GoogleFonts.montserrat(
                          fontSize: 16,
                          color: Colors.grey[600],
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              )
                  : ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: alerts.length,
                itemBuilder: (context, index) {
                  final alert = alerts[index];
                  final severityColor = getAlertSeverity(alert);

                  return Container(
                    margin: const EdgeInsets.only(bottom: 16),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(16),
                      boxShadow: [
                        BoxShadow(
                          color: severityColor.withOpacity(0.2),
                          blurRadius: 8,
                          offset: const Offset(0, 4),
                        ),
                      ],
                      border: Border.all(
                        color: severityColor.withOpacity(0.3),
                        width: 2,
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // ✨ Header shows alert type (local vs major)
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: severityColor,
                            borderRadius: const BorderRadius.vertical(
                              top: Radius.circular(14),
                            ),
                          ),
                          child: Row(
                            children: [
                              Icon(
                                alert.isLocalToUser
                                    ? Icons.location_on
                                    : Icons.warning_amber,
                                color: Colors.white,
                                size: 20,
                              ),
                              const SizedBox(width: 8),
                              Text(
                                alert.alertTypeDisplay,
                                style: GoogleFonts.montserrat(
                                  color: Colors.white,
                                  fontSize: 14,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                        ),

                        // Main content
                        Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              // ✨ Category badge + Disease name + Case count
                              Row(
                                children: [
                                  // Category badge
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 8, vertical: 4),
                                    decoration: BoxDecoration(
                                      color: severityColor.withOpacity(0.1),
                                      borderRadius: BorderRadius.circular(8),
                                      border: Border.all(
                                        color: severityColor.withOpacity(0.3),
                                        width: 1,
                                      ),
                                    ),
                                    child: Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Icon(
                                          alert.categoryIcon,
                                          size: 12,
                                          color: severityColor,
                                        ),
                                        const SizedBox(width: 4),
                                        Text(
                                          alert.categoryDisplay.toUpperCase(),
                                          style: GoogleFonts.montserrat(
                                            fontSize: 10,
                                            fontWeight: FontWeight.bold,
                                            color: severityColor,
                                            letterSpacing: 0.5,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  // Disease name
                                  Expanded(
                                    child: Text(
                                      alert.disease.toUpperCase(),
                                      style: GoogleFonts.montserrat(
                                        fontSize: 16,
                                        fontWeight: FontWeight.bold,
                                        color: severityColor,
                                      ),
                                    ),
                                  ),
                                  // Case count badge
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 10,
                                      vertical: 5,
                                    ),
                                    decoration: BoxDecoration(
                                      color: severityColor.withOpacity(0.1),
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Text(
                                      '${alert.clusterSize} cases',
                                      style: GoogleFonts.montserrat(
                                        fontSize: 13,
                                        fontWeight: FontWeight.bold,
                                        color: severityColor,
                                      ),
                                    ),
                                  ),
                                ],
                              ),

                              const SizedBox(height: 12),

                              // ✨ UPDATED: Use parsed venue name from AlertItem
                              Row(
                                children: [
                                  Icon(
                                    Icons.place,
                                    size: 18,
                                    color: Colors.grey[600],
                                  ),
                                  const SizedBox(width: 6),
                                  Expanded(
                                    child: Text(
                                      // ✨ Use locationDescription for smart text
                                      // Airborne: "in your neighborhood"
                                      // Others: "Mama Mia Trattoria, Manhattan, NY"
                                      alert.isAirborne
                                          ? alert.locationDescription
                                          : alert.venueName,
                                      style: GoogleFonts.montserrat(
                                        fontSize: 15,
                                        color: Colors.grey[700],
                                        fontWeight: FontWeight.w600,
                                      ),
                                    ),
                                  ),
                                ],
                              ),

                              // ✨ Show spread for major outbreaks
                              if (!alert.isLocalToUser && alert.distinctTractCount > 1) ...[
                                const SizedBox(height: 8),
                                Row(
                                  children: [
                                    Icon(
                                      Icons.map,
                                      size: 16,
                                      color: Colors.grey[600],
                                    ),
                                    const SizedBox(width: 6),
                                    Text(
                                      alert.spreadDisplay,
                                      style: GoogleFonts.montserrat(
                                        fontSize: 13,
                                        color: Colors.grey[600],
                                        fontStyle: FontStyle.italic,
                                      ),
                                    ),
                                  ],
                                ),
                              ],

                              const SizedBox(height: 16),

                              // ✨ Category-based personalized message
                              Text(
                                getCleanMessage(alert),
                                style: GoogleFonts.montserrat(
                                  fontSize: 14,
                                  color: Colors.grey[800],
                                  height: 1.5,
                                ),
                              ),

                              const SizedBox(height: 16),

                              // ✨ Bottom info with "View on Map" button
                              Row(
                                children: [
                                  Icon(
                                    Icons.access_time,
                                    size: 14,
                                    color: Colors.grey[500],
                                  ),
                                  const SizedBox(width: 4),
                                  Expanded(
                                    child: Text(
                                      "Last update: ${alert.lastReportTime.toString().split(' ')[0]}",
                                      style: GoogleFonts.montserrat(
                                        fontSize: 12,
                                        color: Colors.grey[600],
                                      ),
                                    ),
                                  ),

                                  // ✨ View on Map button
                                  GestureDetector(
                                    onTap: () {
                                      Navigator.pushNamed(context, '/dashboard');
                                    },
                                    child: Container(
                                      padding: const EdgeInsets.symmetric(
                                          horizontal: 14, vertical: 8),
                                      decoration: BoxDecoration(
                                        color: severityColor,
                                        borderRadius: BorderRadius.circular(20),
                                        boxShadow: [
                                          BoxShadow(
                                            color: severityColor.withOpacity(0.3),
                                            blurRadius: 4,
                                            offset: const Offset(0, 2),
                                          ),
                                        ],
                                      ),
                                      child: Row(
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          const Icon(
                                            Icons.map,
                                            color: Colors.white,
                                            size: 16,
                                          ),
                                          const SizedBox(width: 6),
                                          Text(
                                            'View on Map',
                                            style: GoogleFonts.montserrat(
                                              fontSize: 13,
                                              color: Colors.white,
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
                          ),
                        ),
                      ],
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),

      // Bottom Navigation
      bottomNavigationBar: Container(
        padding: const EdgeInsets.symmetric(vertical: 20),
        color: const Color(0xFF497CCE),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            GestureDetector(
              onTap: () => Navigator.pushNamedAndRemoveUntil(
                  context, '/home', (route) => false),
              child: const Icon(Icons.home, color: Colors.white, size: 30),
            ),
            GestureDetector(
              onTap: () => Navigator.pushNamed(context, '/generate-report'),
              child: const Icon(Icons.add_circle_outline, color: Colors.white, size: 30),
            ),
            GestureDetector(
              onTap: () => Navigator.pushNamed(context, '/dashboard'),
              child: const Icon(Icons.bar_chart, color: Colors.white, size: 30),
            ),
          ],
        ),
      ),
    );
  }
}