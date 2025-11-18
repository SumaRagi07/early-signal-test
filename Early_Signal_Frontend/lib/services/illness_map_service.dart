import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:firebase_auth/firebase_auth.dart';
import '../models/illness_map_data.dart';

class IllnessMapService {
  static const String _baseUrl = 'https://us-central1-adsp-34002-ip07-early-signal.cloudfunctions.net';

  // Get current illness map data
  static Future<List<IllnessMapPoint>?> getCurrentIllnessMapData({
    required double userLatitude,
    required double userLongitude,
  }) async {
    try {
      print('🗺️ Fetching current illness map data...');
      print('📍 User location: $userLatitude, $userLongitude');

      // NEW: Get Firebase ID token
      final user = FirebaseAuth.instance.currentUser;
      if (user == null) {
        print('❌ No user logged in');
        return [];
      }

      final idToken = await user.getIdToken();

      final response = await http.post(
        Uri.parse('$_baseUrl/getCurrentIllnessMapData'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $idToken', // NEW: Add auth token
        },
        body: jsonEncode({
          'user_latitude': userLatitude,
          'user_longitude': userLongitude,
        }),
      );

      print('🗺️ Map API Response: ${response.statusCode}');

      if (response.statusCode == 200) {
        final jsonData = jsonDecode(response.body);
        print('📊 Raw response success: ${jsonData['success']}');
        print('📊 Raw data length: ${jsonData['data']?.length}');

        if (jsonData['success'] == true) {
          print('✅ Parsing response...');
          final mapResponse = IllnessMapResponse.fromJson(jsonData);
          print('✅ Successfully parsed ${mapResponse.data.length} map points');

          // Log each point for debugging
          for (var point in mapResponse.data) {
            print('📍 Point: ${point.category} at ${point.latitude}, ${point.longitude} (${point.caseCount} cases)');
          }

          return mapResponse.data;
        } else {
          print('❌ Map API Error: ${jsonData['error']}');
          return [];
        }
      } else if (response.statusCode == 401) {
        print('❌ Authentication failed. Please log in again.');
        return [];
      } else {
        print('❌ Map API HTTP Error: ${response.statusCode}');
        print('❌ Response body: ${response.body}');
        return [];
      }
    } catch (e) {
      print('❌ Map Service Exception: $e');
      print('❌ Exception stack trace: ${StackTrace.current}');
      return [];
    }
  }

  // Get exposure illness map data
  static Future<List<IllnessMapPoint>?> getExposureIllnessMapData({
    required double userLatitude,
    required double userLongitude,
  }) async {
    try {
      print('🗺️ Fetching exposure illness map data...');
      print('📍 User location: $userLatitude, $userLongitude');

      // NEW: Get Firebase ID token
      final user = FirebaseAuth.instance.currentUser;
      if (user == null) {
        print('❌ No user logged in');
        return [];
      }

      final idToken = await user.getIdToken();

      final response = await http.post(
        Uri.parse('$_baseUrl/getExposureIllnessMapData'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $idToken', // NEW: Add auth token
        },
        body: jsonEncode({
          'user_latitude': userLatitude,
          'user_longitude': userLongitude,
        }),
      );

      print('🗺️ Exposure Map API Response: ${response.statusCode}');

      if (response.statusCode == 200) {
        final jsonData = jsonDecode(response.body);
        print('📊 Raw exposure response success: ${jsonData['success']}');
        print('📊 Raw exposure data length: ${jsonData['data']?.length}');

        if (jsonData['success'] == true) {
          print('✅ Parsing exposure response...');
          final mapResponse = IllnessMapResponse.fromJson(jsonData);
          print('✅ Successfully parsed ${mapResponse.data.length} exposure points');

          // Log each exposure point for debugging
          for (var point in mapResponse.data) {
            print('📍 Exposure Point: ${point.category} at ${point.exposureLocationName} (${point.caseCount} cases)');
          }

          return mapResponse.data;
        } else {
          print('❌ Exposure Map API Error: ${jsonData['error']}');
          return [];
        }
      } else if (response.statusCode == 401) {
        print('❌ Authentication failed. Please log in again.');
        return [];
      } else {
        print('❌ Exposure Map API HTTP Error: ${response.statusCode}');
        print('❌ Response body: ${response.body}');
        return [];
      }
    } catch (e) {
      print('❌ Exposure Map Service Exception: $e');
      print('❌ Exception stack trace: ${StackTrace.current}');
      return [];
    }
  }
}