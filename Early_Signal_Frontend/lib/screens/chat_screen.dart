import 'package:flutter/material.dart';
import '../services/chat_service.dart';

class ChatScreen extends StatefulWidget {
  @override
  _ChatScreenState createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final List<String> _messages = ["👋 Welcome! Describe your symptoms..."];
  final TextEditingController _controller = TextEditingController();

  void _sendMessage() async {
    final text = _controller.text;
    if (text.isEmpty) return;

    setState(() {
      _messages.add("You: $text");
      _controller.clear();
    });

    final response = await ChatService.sendMessage(text);
    setState(() => _messages.add("Bot: $response"));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('EarlySignal Chat')),
      body: Column(
        children: [
          Expanded(
            child: ListView(
              children: _messages.map((msg) => Text(msg)).toList(),
            ),
          ),
          TextField(
            controller: _controller,
            onSubmitted: (_) => _sendMessage(),
            decoration: InputDecoration(
              hintText: 'Type symptoms...',
              suffixIcon: IconButton(
                icon: Icon(Icons.send),
                onPressed: _sendMessage,
              ),
            ),
          ),
        ],
      ),
    );
  }
}