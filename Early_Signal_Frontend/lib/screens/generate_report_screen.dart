import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:geolocator/geolocator.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'dart:convert';

class GenerateReportScreen extends StatefulWidget {
  @override
  _GenerateReportScreenState createState() => _GenerateReportScreenState();
}

class _GenerateReportScreenState extends State<GenerateReportScreen> {
  final TextEditingController _inputController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final FocusNode _inputFocusNode = FocusNode();

  List<Map<String, dynamic>> messages = [];
  late String sessionId;
  bool isLoading = false;
  String? shownDiagnosisId;
  bool reportSubmitted = false;
  bool conversationEnded = false;

  // GPS location tracking
  Position? _currentPosition;
  bool _locationPermissionGranted = false;
  bool _locationFetched = false;

  // Collapsible card states
  bool _careTipsExpanded = false;
  bool _medicalHelpExpanded = false;

// Typing indicator state
  bool _showTypingIndicator = false;

  // User ID from Firebase Auth
  String? _userId;

  @override
  void initState() {
    super.initState();
    sessionId = DateTime.now().millisecondsSinceEpoch.toString();

    _getUserId();
    _getCurrentLocation();

    messages.add({
      "sender": "bot",
      "text": "👋 Welcome to EarlySignal Health Tracker!\n\nI'm here to help you report your symptoms and track potential disease exposure.\n\n💬 Please describe your symptoms and how many days ago they began.",
      "timestamp": DateTime.now(),
    });

    // Auto-focus on input field after build
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _inputFocusNode.requestFocus();
    });
  }

  @override
  void dispose() {
    _inputController.dispose();
    _scrollController.dispose();
    _inputFocusNode.dispose();
    super.dispose();
  }

  Future<void> _getUserId() async {
    try {
      User? user = FirebaseAuth.instance.currentUser;
      if (user != null) {
        setState(() {
          _userId = user.uid;
        });
        print('✅ [Backend] User ID obtained: $_userId');
      } else {
        print('⚠️ [Backend] No user logged in, using fallback user_id = 1');
        setState(() {
          _userId = null;
        });
      }
    } catch (e) {
      print('❌ [Backend] Error getting user ID: $e, using fallback');
      setState(() {
        _userId = null;
      });
    }
  }

  Future<void> _getCurrentLocation() async {
    try {
      bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        print('📍 Location services are disabled');
        setState(() => _locationFetched = true);
        return;
      }

      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
        if (permission == LocationPermission.denied) {
          print('📍 Location permission denied');
          setState(() => _locationFetched = true);
          return;
        }
      }

      if (permission == LocationPermission.deniedForever) {
        print('📍 Location permission denied forever');
        setState(() => _locationFetched = true);
        return;
      }

      Position position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: Duration(seconds: 10),
      );

      setState(() {
        _currentPosition = position;
        _locationPermissionGranted = true;
        _locationFetched = true;
      });

      print('✅ Location obtained: ${position.latitude}, ${position.longitude}');
    } catch (e) {
      print('❌ Error getting location: $e');
      setState(() => _locationFetched = true);
    }
  }

  Future<void> sendToBackend(String text) async {
    final userMessage = text.trim();

    if (userMessage.isEmpty || isLoading || conversationEnded) return;

    // Clear input and immediately refocus
    _inputController.clear();
    _inputFocusNode.requestFocus();

    setState(() {
      messages.add({
        "sender": "user",
        "text": userMessage,
        "timestamp": DateTime.now(),
      });
      isLoading = true;
    });

    _scrollToBottom();

    //final uri = Uri.parse("http://10.0.2.2:8000/chat");
    final uri = Uri.parse("http://localhost:8000/chat");

    final body = {
      "user_input": userMessage,
      "session_id": sessionId,
      if (_userId != null) "user_id": _userId,
      if (_currentPosition != null) "current_latitude": _currentPosition!.latitude,
      if (_currentPosition != null) "current_longitude": _currentPosition!.longitude,
    };

    print("📤 Sending to backend: ${body.keys.toList()}");
    if (_userId != null) {
      print("👤 User ID: $_userId");
    }
    if (_currentPosition != null) {
      print("📍 GPS: (${_currentPosition!.latitude}, ${_currentPosition!.longitude})");
    }

    try {
      final response = await http.post(
        uri,
        headers: {"Content-Type": "application/json"},
        body: jsonEncode(body),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        print("✅ Backend response: $data");

        // ========================================
        // STEP 1: Display follow-up question - IMMEDIATE
        // ========================================
        final botReply = data["console_output"];
        if (botReply != null && botReply.toString().trim().isNotEmpty) {
          setState(() {
            messages.add({
              "sender": "bot",
              "text": botReply.toString(),
              "timestamp": DateTime.now(),
            });
          });
          _scrollToBottom();
        }

        // ========================================
        // STEP 2: Show diagnosis - IMMEDIATE
        // ========================================
        if (data["diagnosis"] != null && data["diagnosis"] is Map) {
          final diagnosis = data["diagnosis"];
          final diagnosisName = diagnosis["final_diagnosis"] ?? "";
          final confidence = diagnosis["confidence"];
          final category = diagnosis["illness_category"] ?? "unknown";

          if (diagnosisName.isNotEmpty && shownDiagnosisId != diagnosisName) {
            shownDiagnosisId = diagnosisName;
            final clusterValidated = diagnosis["cluster_validated"] == true;

            if (!clusterValidated) {
              if (botReply == null || !botReply.toString().contains(diagnosisName)) {
                setState(() {
                  messages.add({
                    "sender": "bot",
                    "text": "📊 Preliminary Diagnosis\n\n"
                        "🏥 Condition: $diagnosisName\n"
                        "📈 Confidence: ${(confidence * 100).toStringAsFixed(0)}%\n"
                        "🏷️ Category: ${category.toUpperCase()}",
                    "timestamp": DateTime.now(),
                    "type": "diagnosis",
                  });
                });
                _scrollToBottom();
              }
            }
          }
        }

        // ========================================
        // STEP 3: Show cluster validation - IMMEDIATE (no scroll)
        // ========================================
        if (data["cluster_validation"] != null && data["cluster_validation"] is Map) {
          final clusterValidation = data["cluster_validation"];
          final clusterMessage = clusterValidation["console_output"];

          if (clusterMessage != null && clusterMessage.toString().trim().isNotEmpty) {
            if (botReply == null || !botReply.toString().contains("OUTBREAK")) {
              setState(() {
                messages.add({
                  "sender": "bot",
                  "text": clusterMessage.toString(),
                  "timestamp": DateTime.now(),
                  "type": "alert",
                });
              });
              _scrollToBottom();
            }
          }
        }

        // ========================================
        // STEP 4: Care advice with typing indicators and delays
        // ========================================
        if (data["care_advice"] != null && data["care_advice"] is Map) {
          final tips = data["care_advice"]["self_care_tips"] ?? [];
          final warning = data["care_advice"]["when_to_seek_help"] ?? "";

          // 💊 Self-Care Tips - 3s gap + 4s typing = 7s total
          if (tips is List && tips.isNotEmpty) {
            // Show typing indicator AFTER 3 second gap
            Future.delayed(Duration(seconds: 3), () {
              if (mounted) {
                setState(() {
                  messages.add({
                    "sender": "bot",
                    "type": "typing",
                    "timestamp": DateTime.now(),
                  });
                });
                _scrollToBottom();
              }
            });

            // After 3s gap + 4s typing, show care tips preview
            Future.delayed(Duration(seconds: 7), () {
              if (mounted) {
                setState(() {
                  // Remove typing indicator
                  messages.removeWhere((msg) => msg["type"] == "typing");

                  // Add care tips preview
                  final preview = tips.take(2).map((t) => "• $t").join("\n");
                  final fullContent = tips.map((t) => "• $t").toList();

                  messages.add({
                    "sender": "bot",
                    "type": "care_preview",
                    "preview": preview + "...",
                    "fullContent": fullContent,
                    "timestamp": DateTime.now(),
                  });
                });
                _scrollToBottom();
              }
            });
          }

          // ⚠️ When to Seek Help - 7s + 2s typing = 9s total
          if (warning.isNotEmpty) {
            // Show typing indicator at 7s
            Future.delayed(Duration(seconds: 7), () {
              if (mounted) {
                Future.delayed(Duration(milliseconds: 100), () {
                  if (mounted) {
                    setState(() {
                      messages.add({
                        "sender": "bot",
                        "type": "typing",
                        "timestamp": DateTime.now(),
                      });
                    });
                    _scrollToBottom();
                  }
                });
              }
            });

            // After 9 seconds total, remove typing and show medical help preview
            Future.delayed(Duration(seconds: 9), () {
              if (mounted) {
                setState(() {
                  // Remove typing indicator
                  messages.removeWhere((msg) => msg["type"] == "typing");

                  // Add medical help preview
                  final preview = warning.length > 100
                      ? warning.substring(0, 100) + "..."
                      : warning;

                  messages.add({
                    "sender": "bot",
                    "type": "warning_preview",
                    "preview": preview,
                    "fullContent": [warning],
                    "timestamp": DateTime.now(),
                  });
                });
                _scrollToBottom();
              }
            });
          }
        }

        // ========================================
        // STEP 5: Report submission - 9s + 2s typing = 11s total
        // ========================================
        if (data["report"] != null && data["report"] is Map && !reportSubmitted) {
          final report = data["report"];

          // Show typing at 9s
          Future.delayed(Duration(seconds: 9), () {
            if (mounted) {
              Future.delayed(Duration(milliseconds: 100), () {
                if (mounted) {
                  setState(() {
                    messages.add({
                      "sender": "bot",
                      "type": "typing",
                      "timestamp": DateTime.now(),
                    });
                  });
                  _scrollToBottom();
                }
              });
            }
          });

          // Show report at 11s
          Future.delayed(Duration(seconds: 11), () {
            if (mounted && !reportSubmitted) {
              setState(() {
                // Remove typing indicator
                messages.removeWhere((msg) => msg["type"] == "typing");

                reportSubmitted = true;
                messages.add({
                  "sender": "bot",
                  "text": "✅ Report Successfully Submitted\n\n"
                      "Your health report has been recorded in our tracking system.\n\n"
                      "📍 Your Location: ${report["current_location_name"] ?? "Not available"}\n"
                      "🧭 Exposure Location: ${report["exposure_location_name"] ?? "Not specified"}\n\n"
                      "Thank you for helping us track public health trends! 🙏",
                  "timestamp": DateTime.now(),
                  "type": "success",
                });
                conversationEnded = true;
              });
              _scrollToBottom();

              // ========================================
              // STEP 6: Conversation complete - 11s + 1s typing = 12s total
              // ========================================
              // Show typing at 11s
              Future.delayed(Duration(milliseconds: 100), () {
                if (mounted) {
                  setState(() {
                    messages.add({
                      "sender": "bot",
                      "type": "typing",
                      "timestamp": DateTime.now(),
                    });
                  });
                  _scrollToBottom();
                }
              });

              // Show completion message at 12s (1s after report)
              Future.delayed(Duration(seconds: 1), () {
                if (mounted) {
                  setState(() {
                    // Remove typing indicator
                    messages.removeWhere((msg) => msg["type"] == "typing");

                    messages.add({
                      "sender": "bot",
                      "text": "🔄 Conversation Complete\n\n"
                          "To start a new health report, please tap the refresh button in the top-right corner.",
                      "timestamp": DateTime.now(),
                      "type": "system",
                    });
                  });
                  _scrollToBottom();
                }
              });
            }
          });
        }

      } else {
        setState(() {
          messages.add({
            "sender": "bot",
            "text": "❌ Server error: ${response.statusCode}\n${response.reasonPhrase ?? ""}",
            "timestamp": DateTime.now(),
            "type": "error",
          });
        });
        _scrollToBottom();
      }
    } catch (e) {
      print("❌ Exception: $e");
      setState(() {
        messages.add({
          "sender": "bot",
          "text": "❌ Connection error. Please check if the backend server is running.",
          "timestamp": DateTime.now(),
          "type": "error",
        });
      });
      _scrollToBottom();
    } finally {
      setState(() => isLoading = false);

      // Always keep focus on input unless conversation ended
      if (!conversationEnded) {
        Future.delayed(Duration(milliseconds: 150), () {
          if (mounted && !conversationEnded) {
            _inputFocusNode.requestFocus();
          }
        });
      }
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: Duration(milliseconds: 400),
          curve: Curves.easeOutCubic,
        );
      }
    });
  }

  void resetSession() {
    setState(() {
      _inputController.clear();
      messages.clear();
      sessionId = DateTime.now().millisecondsSinceEpoch.toString();
      isLoading = false;
      shownDiagnosisId = null;
      reportSubmitted = false;
      conversationEnded = false;
      messages.add({
        "sender": "bot",
        "text": "👋 Welcome to EarlySignal Health Tracker!\n\nI'm here to help you report your symptoms and track potential disease exposure.\n\n💬 Please describe your symptoms and how many days ago they began.",
        "timestamp": DateTime.now(),
      });
    });

    _getCurrentLocation();

    // Re-focus input
    Future.delayed(Duration(milliseconds: 200), () {
      if (mounted) {
        _inputFocusNode.requestFocus();
      }
    });
  }

  Widget _buildMessageBubble(Map<String, dynamic> message) {
    final isUser = message["sender"] == "user";
    final alignment = isUser ? Alignment.centerRight : Alignment.centerLeft;
    final type = message["type"] ?? "normal";

    // Handle typing indicator
    if (type == "typing") {
      return _buildTypingIndicator();
    }

    // Handle collapsible care tips
    if (type == "care_preview") {
      return _buildCollapsibleCard(
        title: "💊 Self-Care Recommendations",
        previewText: message["preview"] ?? "",
        fullContent: List<String>.from(message["fullContent"] ?? []),
        type: "care",
        isExpanded: _careTipsExpanded,
        onToggle: () {
          setState(() {
            _careTipsExpanded = !_careTipsExpanded;
          });
        },
      );
    }

    // Handle collapsible medical help
    if (type == "warning_preview") {
      return _buildCollapsibleCard(
        title: "⚠️ When to Seek Medical Help",
        previewText: message["preview"] ?? "",
        fullContent: List<String>.from(message["fullContent"] ?? []),
        type: "warning",
        isExpanded: _medicalHelpExpanded,
        onToggle: () {
          setState(() {
            _medicalHelpExpanded = !_medicalHelpExpanded;
          });
        },
      );
    }

    // Regular message bubbles (existing code)
    Color bubbleColor;
    Color textColor = Colors.black87;

    if (isUser) {
      bubbleColor = Color(0xFF2196F3);
      textColor = Colors.white;
    } else {
      switch (type) {
        case "diagnosis":
          bubbleColor = Color(0xFFE3F2FD);
          break;
        case "alert":
          bubbleColor = Color(0xFFFFF3E0);
          break;
        case "warning":
          bubbleColor = Color(0xFFFFEBEE);
          break;
        case "care":
          bubbleColor = Color(0xFFE8F5E9);
          break;
        case "success":
          bubbleColor = Color(0xFFC8E6C9);
          break;
        case "system":
          bubbleColor = Color(0xFFF5F5F5);
          break;
        case "error":
          bubbleColor = Color(0xFFFFCDD2);
          break;
        default:
          bubbleColor = Color(0xFFF5F5F5);
      }
    }

    return Align(
      alignment: alignment,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.80,
        ),
        margin: const EdgeInsets.symmetric(vertical: 6, horizontal: 12),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: bubbleColor,
          borderRadius: BorderRadius.only(
            topLeft: Radius.circular(20),
            topRight: Radius.circular(20),
            bottomLeft: isUser ? Radius.circular(20) : Radius.circular(4),
            bottomRight: isUser ? Radius.circular(4) : Radius.circular(20),
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.08),
              blurRadius: 6,
              offset: Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SelectableText(
              message["text"],
              style: TextStyle(
                fontSize: 15,
                height: 1.4,
                color: textColor,
                fontWeight: type == "diagnosis" || type == "success"
                    ? FontWeight.w500
                    : FontWeight.normal,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTypingIndicator() {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.80,
        ),
        margin: const EdgeInsets.symmetric(vertical: 6, horizontal: 12),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: Color(0xFFF5F5F5),
          borderRadius: BorderRadius.only(
            topLeft: Radius.circular(20),
            topRight: Radius.circular(20),
            bottomLeft: Radius.circular(4),
            bottomRight: Radius.circular(20),
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.08),
              blurRadius: 6,
              offset: Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildTypingDot(0),
            SizedBox(width: 4),
            _buildTypingDot(1),
            SizedBox(width: 4),
            _buildTypingDot(2),
            SizedBox(width: 8),
            Text(
              'typing...',
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey[600],
                fontStyle: FontStyle.italic,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTypingDot(int index) {
    return TweenAnimationBuilder(
      tween: Tween<double>(begin: 0.0, end: 1.0),
      duration: Duration(milliseconds: 600),
      curve: Curves.easeInOut,
      builder: (context, double value, child) {
        return Opacity(
          opacity: 0.3 + (0.7 * ((value + (index * 0.3)) % 1.0)),
          child: Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: Colors.grey[600],
              shape: BoxShape.circle,
            ),
          ),
        );
      },
      onEnd: () {
        if (mounted) {
          setState(() {}); // Rebuild to restart animation
        }
      },
    );
  }

  Widget _buildCollapsibleCard({
    required String title,
    required String previewText,
    required List<String> fullContent,
    required String type,
    required bool isExpanded,
    required VoidCallback onToggle,
  }) {
    final color = type == "care" ? Color(0xFFE8F5E9) : Color(0xFFFFEBEE);
    final textColor = Colors.black87;
    final iconColor = type == "care" ? Colors.green[700] : Colors.orange[700];

    return Align(
      alignment: Alignment.centerLeft,
      child: GestureDetector(
        onTap: onToggle,
        child: Container(
          constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.80,
          ),
          margin: const EdgeInsets.symmetric(vertical: 6, horizontal: 12),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.only(
              topLeft: Radius.circular(20),
              topRight: Radius.circular(20),
              bottomLeft: Radius.circular(4),
              bottomRight: Radius.circular(20),
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.08),
                blurRadius: 6,
                offset: Offset(0, 2),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Title
              Text(
                title,
                style: TextStyle(
                  fontSize: 15,
                  height: 1.4,
                  color: textColor,
                  fontWeight: FontWeight.w600,
                ),
              ),
              SizedBox(height: 8),

              // Content (preview or full)
              if (!isExpanded) ...[
                Text(
                  previewText,
                  style: TextStyle(
                    fontSize: 15,
                    height: 1.4,
                    color: textColor,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                SizedBox(height: 8),
                Row(
                  children: [
                    Icon(Icons.arrow_drop_down, color: iconColor, size: 20),
                    SizedBox(width: 4),
                    Text(
                      'Tap to view all ${fullContent.length} ${type == "care" ? "tips" : "details"}',
                      style: TextStyle(
                        fontSize: 13,
                        color: iconColor,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ] else ...[
                ...fullContent.map((item) => Padding(
                  padding: const EdgeInsets.only(bottom: 8.0),
                  child: Text(
                    item,
                    style: TextStyle(
                      fontSize: 15,
                      height: 1.4,
                      color: textColor,
                    ),
                  ),
                )).toList(),
                SizedBox(height: 4),
                Row(
                  children: [
                    Icon(Icons.arrow_drop_up, color: iconColor, size: 20),
                    SizedBox(width: 4),
                    Text(
                      'Tap to collapse',
                      style: TextStyle(
                        fontSize: 13,
                        color: iconColor,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: Colors.grey[50],
      appBar: AppBar(
        elevation: 0,
        backgroundColor: Colors.white,
        centerTitle: true,
        title: Image.asset(
          'assets/images/logo2.png',
          height: 75,
          fit: BoxFit.contain,
          errorBuilder: (context, error, stackTrace) {
            // Fallback if logo not found
            return Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [Color(0xFF2196F3), Color(0xFF1976D2)],
                ),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(
                Icons.health_and_safety,
                color: Colors.white,
                size: 24,
              ),
            );
          },
        ),
        actions: [
          // GPS Status Indicator
          if (_locationFetched)
            Padding(
              padding: const EdgeInsets.only(right: 4.0),
              child: Center(
                child: Tooltip(
                  message: _locationPermissionGranted
                      ? "GPS enabled"
                      : "GPS disabled",
                  child: Icon(
                    _locationPermissionGranted
                        ? Icons.location_on
                        : Icons.location_off,
                    color: _locationPermissionGranted
                        ? Colors.green
                        : Colors.grey,
                    size: 20,
                  ),
                ),
              ),
            ),
          // Refresh Button
          IconButton(
            icon: Icon(Icons.refresh, color: Color(0xFF1976D2)),
            tooltip: "Start New Report",
            onPressed: resetSession,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Chat Messages Area
            Expanded(
              child: ListView.builder(
                controller: _scrollController,
                padding: const EdgeInsets.only(top: 12, bottom: 16),
                physics: BouncingScrollPhysics(),
                itemCount: messages.length + (isLoading ? 1 : 0),
                itemBuilder: (context, idx) {
                  if (idx < messages.length) {
                    return _buildMessageBubble(messages[idx]);
                  } else {
                    // Loading indicator
                    return Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      child: Row(
                        children: [
                          SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              valueColor: AlwaysStoppedAnimation<Color>(
                                Color(0xFF2196F3),
                              ),
                            ),
                          ),
                          SizedBox(width: 12),
                          Text(
                            "Analyzing...",
                            style: TextStyle(
                              color: Colors.grey[600],
                              fontSize: 14,
                              fontStyle: FontStyle.italic,
                            ),
                          ),
                        ],
                      ),
                    );
                  }
                },
              ),
            ),

            // Divider
            Divider(height: 1, thickness: 1, color: Colors.grey[300]),

            // Input Area
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              color: Colors.white,
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _inputController,
                      focusNode: _inputFocusNode,
                      enabled: !isLoading && !conversationEnded,
                      textInputAction: TextInputAction.send,
                      onSubmitted: (value) {
                        // Send message when Enter is pressed
                        sendToBackend(value);
                      },
                      style: TextStyle(fontSize: 15),
                      decoration: InputDecoration(
                        hintText: conversationEnded
                            ? "Conversation complete. Tap refresh to start new report."
                            : "Type your message...",
                        hintStyle: TextStyle(
                          color: conversationEnded ? Colors.grey : Colors.grey[400],
                          fontSize: 14,
                        ),
                        filled: true,
                        fillColor: conversationEnded
                            ? Colors.grey[200]
                            : Colors.grey[100],
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(24),
                          borderSide: BorderSide.none,
                        ),
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: 20,
                          vertical: 12,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  // Send Button
                  Material(
                    color: (isLoading || conversationEnded)
                        ? Colors.grey[300]
                        : Color(0xFF2196F3),
                    borderRadius: BorderRadius.circular(24),
                    child: InkWell(
                      borderRadius: BorderRadius.circular(24),
                      onTap: (isLoading || conversationEnded)
                          ? null
                          : () => sendToBackend(_inputController.text),
                      child: Container(
                        padding: const EdgeInsets.all(14),
                        child: Icon(
                          Icons.send,
                          color: Colors.white,
                          size: 22,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}