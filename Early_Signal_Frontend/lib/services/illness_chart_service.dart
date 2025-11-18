import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:firebase_auth/firebase_auth.dart';
import '../models/illness_data.dart';

class IllnessChartService {
  static const String _baseUrl = 'https://us-central1-adsp-34002-ip07-early-signal.cloudfunctions.net';

  static Future<PieChartResponse?> getPieChartData({
    required double latitude,
    required double longitude,
    double radiusMiles = 5.0,
  }) async {
    try {
      // NEW: Get Firebase ID token
      final user = FirebaseAuth.instance.currentUser;
      if (user == null) {
        print('❌ No user logged in');
        return null;
      }

      final idToken = await user.getIdToken();

      final response = await http.post(
        Uri.parse('$_baseUrl/getIllnessPieChartData'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $idToken', // NEW: Add auth token
        },
        body: jsonEncode({
          'latitude': latitude,
          'longitude': longitude,
          'radius_miles': radiusMiles,
        }),
      );

      if (response.statusCode == 200) {
        final jsonData = jsonDecode(response.body);
        return PieChartResponse.fromJson(jsonData);
      } else if (response.statusCode == 401) {
        print('❌ Authentication failed. Please log in again.');
        return null;
      } else {
        print('❌ API Error: ${response.statusCode} - ${response.body}');
        return null;
      }
    } catch (e) {
      print('❌ Network Error: $e');
      return null;
    }
  }
}