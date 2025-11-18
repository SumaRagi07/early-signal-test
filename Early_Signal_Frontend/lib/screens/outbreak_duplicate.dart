import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'home_screen.dart'; // Ensure this path is correct

class OutbreakDashboardPage extends StatelessWidget {
  const OutbreakDashboardPage({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey[200],
      body: SafeArea(
        child: SingleChildScrollView(
          child: Column(
            children: [
              // 🔵 Logo bar (same as HomeScreen)
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

              // ✅ PIE CHART FIRST
              const Padding(
                padding: EdgeInsets.all(12.0),
                child: Text(
                  "Pie Chart of Illnesses",
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
              ),
              _buildWebChart('https://lookerstudio.google.com/embed/reporting/06320650-7c9d-4be5-a2c0-b662eee722c1/page/PcNJF'),

              // ✅ CONTAGIOUS REPORTS SECOND
              const Padding(
                padding: EdgeInsets.all(12.0),
                child: Text(
                  "Nearby Contagious Reports",
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
              ),
              _buildWebChart('https://lookerstudio.google.com/embed/reporting/cc7a02ea-29ba-4507-b89e-8a1963faf099/page/lrTIF'),

              // ✅ EXPOSURE MAP THIRD
              const Padding(
                padding: EdgeInsets.all(12.0),
                child: Text(
                  "Exposure Map",
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
              ),
              _buildWebChart('https://lookerstudio.google.com/embed/reporting/b22bc5ac-0ce2-41c1-8f33-11493a99093e/page/7cNJF'),

              const SizedBox(height: 20),

              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: const [
                    _CaseCard(count: "8", label: "Flu"),
                    _CaseCard(count: "4", label: "Salmonella"),
                  ],
                ),
              ),

              const SizedBox(height: 20),
            ],
          ),
        ),
      ),
      bottomNavigationBar: Container(
        padding: const EdgeInsets.symmetric(vertical: 20),
        color: const Color(0xFF497CCE),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            GestureDetector(
              onTap: () {
                Navigator.pushReplacement(
                  context,
                  MaterialPageRoute(builder: (_) => const HomeScreen()),
                );
              },
              child: const Icon(Icons.home, color: Colors.white, size: 30),
            ),
            const Icon(Icons.add_circle_outline, color: Colors.white, size: 30),
            const Icon(Icons.bar_chart, color: Colors.white, size: 30),
          ],
        ),
      ),
    );
  }

  Widget _buildWebChart(String url) {
    final controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..loadRequest(Uri.parse(url));

    return Container(
      height: 280,
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade300),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: WebViewWidget(controller: controller),
      ),
    );
  }
}

class _CaseCard extends StatelessWidget {
  final String count;
  final String label;

  const _CaseCard({required this.count, required this.label});

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 2,
      child: Container(
        width: 140,
        height: 90,
        padding: const EdgeInsets.all(12),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              "$count Cases",
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 6),
            Text(label, style: const TextStyle(fontStyle: FontStyle.italic)),
          ],
        ),
      ),
    );
  }
}