class IllnessChartData {
  final String category;
  final int caseCount;
  final double percentage;

  IllnessChartData({
    required this.category,
    required this.caseCount,
    required this.percentage,
  });

  factory IllnessChartData.fromJson(Map<String, dynamic> json) {
    return IllnessChartData(
      category: json['category'] ?? 'Unknown',
      caseCount: int.parse(json['case_count'].toString()),
      percentage: double.parse(json['percentage'].toString()),
    );
  }
}

class PieChartResponse {
  final bool success;
  final List<IllnessChartData> data;
  final Map<String, dynamic> location;
  final int totalCategories;
  final int totalCases;

  PieChartResponse({
    required this.success,
    required this.data,
    required this.location,
    required this.totalCategories,
    required this.totalCases,
  });

  factory PieChartResponse.fromJson(Map<String, dynamic> json) {
    return PieChartResponse(
      success: json['success'] ?? false,
      data: (json['data'] as List)
          .map((item) => IllnessChartData.fromJson(item))
          .toList(),
      location: json['location'] ?? {},
      totalCategories: json['total_categories'] ?? 0,
      totalCases: json['total_cases'] ?? 0,
    );
  }
}