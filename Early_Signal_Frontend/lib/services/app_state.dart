import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import '../models/alert_item.dart';

class AppState extends ChangeNotifier {
  LatLng? _currentPosition;
  List<AlertItem> _alerts = [];
  bool _isFetching = false;
  bool _hasInitialData = false;
  GoogleMapController? _mapController;

  // Getters
  LatLng? get currentPosition => _currentPosition;
  List<AlertItem> get alerts => _alerts;
  bool get isFetching => _isFetching;
  bool get hasInitialData => _hasInitialData;
  GoogleMapController? get mapController => _mapController;

  // Setters
  void setPosition(LatLng position) {
    _currentPosition = position;
    notifyListeners();
  }

  void setAlerts(List<AlertItem> alerts) {
    _alerts = alerts;
    _hasInitialData = true;
    notifyListeners();
  }

  void setFetching(bool fetching) {
    _isFetching = fetching;
    notifyListeners();
  }

  void setMapController(GoogleMapController controller) {
    _mapController = controller;
  }

  void clearAll() {
    _currentPosition = null;
    _alerts = [];
    _hasInitialData = false;
    _mapController?.dispose();
    _mapController = null;
    notifyListeners();
  }
}