import 'package:http/http.dart' as http;
import 'dart:convert';

class ChatService {
  static const String _baseUrl = 'http://10.0.2.2:8080'; // For Android emulator

  static Future<String> sendMessage(String message) async {
    final response = await http.post(
      Uri.parse('$_baseUrl/chat'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'user_input': message}),
    );
    return jsonDecode(response.body)['response'];
  }
}