import 'package:flutter/material.dart';

class AlertItem {
  final String exposureClusterId;
  final String disease;
  final String category;
  final String locationTag;
  final String locationName;
  final int clusterSize;
  final double consensusRatio;
  final String alertMessage;
  final DateTime lastReportTime;
  final bool isLocalToUser;
  final int distinctTractCount;
  final List<String> distinctStateNames;

  AlertItem({
    required this.exposureClusterId,
    required this.disease,
    this.category = 'Other',
    required this.locationTag,
    this.locationName = '',
    required this.clusterSize,
    required this.consensusRatio,
    required this.alertMessage,
    required this.lastReportTime,
    this.isLocalToUser = false,
    this.distinctTractCount = 1,
    this.distinctStateNames = const [],
  });

  factory AlertItem.fromJson(Map<String, dynamic> json) {
    return AlertItem(
      exposureClusterId: json['exposure_cluster_id'] ?? '',
      disease: json['predominant_disease'] ?? 'Unknown',
      category: json['predominant_category'] ?? 'Other',
      locationTag: json['sample_exposure_tag'] ?? '',
      locationName: json['location_name'] ?? '',
      clusterSize: json['cluster_size'] ?? 0,
      consensusRatio: (json['consensus_ratio'] ?? 0.0).toDouble(),
      alertMessage: json['alert_message'] ?? '',
      lastReportTime: DateTime.tryParse(json['last_report_ts']?['value'] ?? '') ?? DateTime.now(),
      isLocalToUser: json['is_local_to_user'] ?? false,
      distinctTractCount: json['distinct_tract_count'] ?? 1,
      distinctStateNames: json['distinct_state_names'] != null
          ? List<String>.from(json['distinct_state_names'])
          : [],
    );
  }

  // ✨ NEW: Parse full venue name from exposure tag
  // Format: venue_city_state_date_lat_lng
  // Examples:
  // - mellon_park_pittsburgh_pa_2025-10-02_40.4406_-79.9195
  // - mama_mia_trattoria_times_square_manhattan_ny_2025-10-14_40.758_-73.9855
  // - millennium_park_2025-10-25_41.8826_-87.6225 (no city/state)
  String get venueName {
    if (locationTag.isEmpty) return 'Unknown Location';

    try {
      String tag = locationTag;

      // Step 1: Remove coordinates at the end
      // Pattern: _lat_lng where lat/lng are numbers with optional decimals
      tag = tag.replaceAll(RegExp(r'_-?\d+\.?\d*_-?\d+\.?\d*$'), '');

      // Step 2: Remove date pattern (YYYY-MM-DD)
      tag = tag.replaceAll(RegExp(r'_\d{4}-\d{2}-\d{2}$'), '');

      // Now we have: venue_city_state OR venue_city OR just venue
      List<String> parts = tag.split('_');

      if (parts.isEmpty) return 'Unknown Location';

      // Step 3: Detect state (last part is 2 letters and all lowercase)
      String? state;
      if (parts.length >= 1) {
        String lastPart = parts[parts.length - 1];
        if (lastPart.length == 2 && RegExp(r'^[a-z]{2}$').hasMatch(lastPart)) {
          state = lastPart.toUpperCase();
          parts.removeLast();
        }
      }

      // Step 4: Detect city (last remaining part after removing state)
      String? city;
      if (parts.length >= 2) {
        city = _capitalize(parts[parts.length - 1]);
        parts.removeLast();
      }

      // Step 5: Everything else is the venue name
      String venue = parts.isEmpty ? 'Unknown Venue' : _capitalize(parts.join(' '));

      // Step 6: Build full location string
      if (state != null && city != null) {
        return '$venue, $city, $state';
      } else if (city != null) {
        return '$venue, $city';
      } else {
        return venue;
      }

    } catch (e) {
      print('❌ Error parsing venue name from: $locationTag - $e');
      return _capitalize(locationTag.replaceAll('_', ' '));
    }
  }

  // ✨ NEW: Get just the venue name without city/state
  // For use in recommendations like "DO NOT eat at [venue]"
  String get venueNameOnly {
    if (locationTag.isEmpty) return 'this location';

    try {
      String tag = locationTag;

      // Remove coordinates
      tag = tag.replaceAll(RegExp(r'_-?\d+\.?\d*_-?\d+\.?\d*$'), '');

      // Remove date
      tag = tag.replaceAll(RegExp(r'_\d{4}-\d{2}-\d{2}$'), '');

      List<String> parts = tag.split('_');
      if (parts.isEmpty) return 'this location';

      // Remove state if present (last part, 2 letters)
      if (parts.length >= 1) {
        String lastPart = parts[parts.length - 1];
        if (lastPart.length == 2 && RegExp(r'^[a-z]{2}$').hasMatch(lastPart)) {
          parts.removeLast();
        }
      }

      // Remove city (last remaining part, if more than 1 part left)
      if (parts.length >= 2) {
        parts.removeLast();
      }

      // Return venue name only
      return parts.isEmpty ? 'this location' : _capitalize(parts.join(' '));

    } catch (e) {
      print('❌ Error parsing venue name only from: $locationTag - $e');
      return 'this location';
    }
  }

  // ✨ NEW: Check if this is an airborne alert
  // Airborne alerts use CURRENT location, not exposure location
  bool get isAirborne {
    return category.toLowerCase() == 'airborne';
  }

  // ✨ NEW: Get appropriate location description based on category
  // Airborne: "in your area" (no specific venue)
  // Others: specific venue name (exposure location)
  String get locationDescription {
    if (isAirborne) {
      // Airborne spreads everywhere, no specific venue to avoid
      return isLocalToUser ? 'in your neighborhood' : 'in your area';
    } else {
      // Other categories: specific exposure location to avoid
      return venueName;
    }
  }

  // ✨ NEW: Get venue-specific warning (only for non-airborne)
  // ✨ NEW: Get venue-specific warning (only for non-airborne)
  String? get venueWarning {
    if (isAirborne) {
      return null; // No specific venue to avoid for airborne
    }

    String venue = venueNameOnly;

    switch (category.toLowerCase()) {
      case 'foodborne':
        return '❌ Consider avoiding $venue for a few days';
      case 'waterborne':
        return '❌ Avoid drinking water near $venue for a few days';
      case 'insect-borne':
        return '⚠️ Avoid $venue during dawn/dusk for a few days';
      case 'direct_contact':
        return '⚠️ Consider avoiding $venue for a few days';
      default:
        return '⚠️ Exercise caution near $venue for a few days';
    }
  }

  // Helper: Capitalize each word properly
  String _capitalize(String text) {
    if (text.isEmpty) return text;

    return text.split(' ').map((word) {
      if (word.isEmpty) return word;

      // Special handling for abbreviations (keep uppercase if all caps and <= 3 chars)
      if (word.length <= 3 && RegExp(r'^[A-Z]+$').hasMatch(word.toUpperCase())) {
        return word.toUpperCase();
      }

      return word[0].toUpperCase() + word.substring(1).toLowerCase();
    }).join(' ');
  }

  // ✨ Category icon
  IconData get categoryIcon {
    switch (category.toLowerCase()) {
      case 'airborne':
        return Icons.air;
      case 'foodborne':
        return Icons.restaurant;
      case 'waterborne':
        return Icons.water_drop;
      case 'insect-borne':
        return Icons.bug_report;
      case 'direct contact':
      case 'direct_contact':
        return Icons.people;
      default:
        return Icons.warning;
    }
  }

  // ✨ Category display name
  String get categoryDisplay {
    switch (category.toLowerCase()) {
      case 'airborne':
        return 'Airborne';
      case 'foodborne':
        return 'Foodborne';
      case 'waterborne':
        return 'Waterborne';
      case 'insect-borne':
        return 'Insect-borne';
      case 'direct contact':
      case 'direct_contact':
        return 'Direct Contact';
      default:
        return 'Other';
    }
  }

  String get confidenceDisplay {
    return '${(consensusRatio * 100).round()}% consensus';
  }

  String get alertTypeDisplay {
    return isLocalToUser ? 'IN YOUR AREA' : 'MAJOR OUTBREAK';
  }

  String get spreadDisplay {
    if (isLocalToUser) {
      return 'In your neighborhood';
    } else if (distinctStateNames.length > 1) {
      return 'Across ${distinctStateNames.length} states';
    } else if (distinctTractCount > 1) {
      return 'Across $distinctTractCount neighborhoods';
    } else {
      return 'Localized outbreak';
    }
  }
}