import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/app_state.dart';
import '../services/illness_map_service.dart';
import '../models/illness_map_data.dart';

class SearchResultsPage extends StatefulWidget {
  final String searchQuery;

  const SearchResultsPage({Key? key, required this.searchQuery}) : super(key: key);

  @override
  State<SearchResultsPage> createState() => _SearchResultsPageState();
}

class _SearchResultsPageState extends State<SearchResultsPage> {
  List<IllnessMapPoint> _currentResults = [];
  List<IllnessMapPoint> _exposureResults = [];
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _performSearch();
  }

  Future<void> _performSearch() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final appState = Provider.of<AppState>(context, listen: false);
      final position = appState.currentPosition;

      if (position != null) {
        // Load both current and exposure data
        final currentData = await IllnessMapService.getCurrentIllnessMapData(
          userLatitude: position.latitude,
          userLongitude: position.longitude,
        );

        final exposureData = await IllnessMapService.getExposureIllnessMapData(
          userLatitude: position.latitude,
          userLongitude: position.longitude,
        );

        // Filter results based on search query
        final query = widget.searchQuery.toLowerCase();

        final filteredCurrent = currentData?.where((point) {
          return point.category.toLowerCase().contains(query) ||
              _matchesSymptoms(query);
        }).toList() ?? [];

        final filteredExposure = exposureData?.where((point) {
          return point.category.toLowerCase().contains(query) ||
              (point.exposureLocationName?.toLowerCase().contains(query) ?? false) ||
              _matchesSymptoms(query);
        }).toList() ?? [];

        setState(() {
          _currentResults = filteredCurrent;
          _exposureResults = filteredExposure;
          _isLoading = false;
        });
      } else {
        setState(() {
          _error = 'Location not available';
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _error = 'Error searching: $e';
        _isLoading = false;
      });
    }
  }

  bool _matchesSymptoms(String query) {
    // Match common symptoms with illness categories
    if (query.contains('stomach') || query.contains('nausea') || query.contains('vomit') || query.contains('diarrhea')) {
      return true;
    }
    if (query.contains('fever') || query.contains('cough') || query.contains('respiratory')) {
      return true;
    }
    if (query.contains('food') || query.contains('poisoning')) {
      return true;
    }
    return false;
  }

  @override
  Widget build(BuildContext context) {
    final totalResults = _currentResults.length + _exposureResults.length;

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        backgroundColor: const Color(0xFF497CCE),
        title: Text(
          'Search: "${widget.searchQuery}"',
          style: const TextStyle(color: Colors.white, fontSize: 18),
        ),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () => Navigator.pop(context),
        ),
        elevation: 0,
      ),
      body: _isLoading
          ? const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(color: Color(0xFF497CCE)),
            SizedBox(height: 16),
            Text('Searching illness reports...'),
          ],
        ),
      )
          : _error != null
          ? Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 64, color: Colors.grey[400]),
            const SizedBox(height: 16),
            Text(_error!, textAlign: TextAlign.center),
          ],
        ),
      )
          : Column(
        children: [
          // Search results header
          Container(
            padding: const EdgeInsets.all(20),
            color: Colors.white,
            child: Row(
              children: [
                Icon(Icons.search, color: Colors.grey[600]),
                const SizedBox(width: 12),
                Text(
                  '$totalResults results found',
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),

          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Current illness reports
                  if (_currentResults.isNotEmpty) ...[
                    _buildSectionHeader('Current Illness Reports', _currentResults.length),
                    const SizedBox(height: 12),
                    ..._currentResults.map((point) => _buildCurrentResultCard(point)),
                    const SizedBox(height: 24),
                  ],

                  // Exposure reports
                  if (_exposureResults.isNotEmpty) ...[
                    _buildSectionHeader('Exposure Reports', _exposureResults.length),
                    const SizedBox(height: 12),
                    ..._exposureResults.map((point) => _buildExposureResultCard(point)),
                  ],

                  // No results
                  if (totalResults == 0) ...[
                    const SizedBox(height: 60),
                    Center(
                      child: Column(
                        children: [
                          Icon(Icons.search_off, size: 64, color: Colors.grey[400]),
                          const SizedBox(height: 16),
                          Text(
                            'No results found for "${widget.searchQuery}"',
                            style: const TextStyle(fontSize: 16),
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Try searching for:\n• Illness types (foodborne, airborne)\n• Symptoms (fever, nausea)\n• Locations (restaurants, Chicago)',
                            style: TextStyle(color: Colors.grey[600]),
                            textAlign: TextAlign.center,
                          ),
                        ],
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title, int count) {
    return Row(
      children: [
        Text(
          title,
          style: const TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.bold,
            color: Color(0xFF1F2937),
          ),
        ),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: const Color(0xFF497CCE),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            count.toString(),
            style: const TextStyle(
              color: Colors.white,
              fontSize: 12,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildCurrentResultCard(IllnessMapPoint point) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey[200]!),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFF10B981).withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.person, color: Color(0xFF10B981), size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${point.category.toUpperCase()} ILLNESS',
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 14,
                        color: Color(0xFF10B981),
                      ),
                    ),
                    Text(
                      'Latitude: ${point.latitude.toStringAsFixed(4)}, Longitude: ${point.longitude.toStringAsFixed(4)}',
                      style: TextStyle(color: Colors.grey[600], fontSize: 12),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFF10B981),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '${point.caseCount}',
                  style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            '${point.caseCount} case${point.caseCount > 1 ? 's' : ''} reported',
            style: TextStyle(color: Colors.grey[600], fontSize: 12),
          ),
        ],
      ),
    );
  }

  Widget _buildExposureResultCard(IllnessMapPoint point) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey[200]!),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFFDC2626).withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.location_on, color: Color(0xFFDC2626), size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${point.category.toUpperCase()} EXPOSURE',
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 14,
                        color: Color(0xFFDC2626),
                      ),
                    ),
                    Text(
                      point.exposureLocationName ?? 'Unknown Location',
                      style: TextStyle(color: Colors.grey[600], fontSize: 12),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFFDC2626),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '${point.caseCount}',
                  style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            '${point.caseCount} exposure${point.caseCount > 1 ? 's' : ''} reported',
            style: TextStyle(color: Colors.grey[600], fontSize: 12),
          ),
        ],
      ),
    );
  }
}