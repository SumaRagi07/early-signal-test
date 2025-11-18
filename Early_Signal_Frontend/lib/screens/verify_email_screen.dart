import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_functions/cloud_functions.dart';

import 'login_screen.dart';
import 'create_account_screen.dart';

class VerifyEmailScreen extends StatefulWidget {
  final String userId;
  final String email;
  final String username;
  final String name;
  final String mobileNumber;

  const VerifyEmailScreen({
    super.key,
    required this.userId,
    required this.email,
    required this.username,
    required this.name,
    required this.mobileNumber,
  });

  @override
  State<VerifyEmailScreen> createState() => _VerifyEmailScreenState();
}

class _VerifyEmailScreenState extends State<VerifyEmailScreen> {
  bool isVerifying = false;
  bool isSuccess = false;
  String statusMessage = "Waiting for email verification...";

  Future<void> checkVerificationAndSubmit() async {
    setState(() {
      isVerifying = true;
      statusMessage = "Checking verification status...";
    });

    await FirebaseAuth.instance.currentUser?.reload();
    final user = FirebaseAuth.instance.currentUser;

    if (user != null && user.emailVerified) {
      try {
        final HttpsCallable callable = FirebaseFunctions.instance.httpsCallable('createUserRecord');
        final result = await callable.call(<String, dynamic>{
          'user_id': widget.userId,
          'email': widget.email,
          'username': widget.username,
          'name': widget.name,
          'mobile_number': widget.mobileNumber,
        });

        final data = result.data;
        debugPrint('Cloud Function response: $data');

        if (data['success'] == true) {
          setState(() {
            isSuccess = true;
            statusMessage = data['message'] ?? "Email verified! Account created.";
          });

          await Future.delayed(const Duration(seconds: 2));
          if (mounted) {
            Navigator.pushReplacement(
              context,
              MaterialPageRoute(builder: (_) => const LoginScreen()),
            );
          }
        } else {
          setState(() {
            statusMessage = "Email verified, but user record creation failed.";
            isVerifying = false;
          });
        }
      } catch (e) {
        setState(() {
          statusMessage = "Verification succeeded but failed to create account.";
          isVerifying = false;
        });
        debugPrint('Function error: $e');
      }
    } else {
      setState(() {
        statusMessage = "Email not verified yet. Please check your inbox.";
        isVerifying = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey[200],
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            const SizedBox(height: 50),
            const Icon(Icons.lock, size: 80, color: Color(0xFF497CCE)),
            const SizedBox(height: 20),
            Text(
              'Confirm your identity',
              style: GoogleFonts.montserrat(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: Colors.black87,
              ),
            ),
            const SizedBox(height: 10),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 40),
              child: Text(
                'Check your email and click on the verification link we sent you. Once verified, tap below to continue.',
                style: GoogleFonts.montserrat(fontSize: 14),
                textAlign: TextAlign.center,
              ),
            ),
            const SizedBox(height: 30),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 40),
              child: ElevatedButton(
                onPressed: isVerifying ? null : checkVerificationAndSubmit,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF497CCE),
                  minimumSize: const Size(double.infinity, 50),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(30),
                  ),
                ),
                child: isVerifying
                    ? const CircularProgressIndicator(color: Colors.white)
                    : Text(
                  'I Verified My Email',
                  style: GoogleFonts.montserrat(
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                    color: Colors.white,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 20),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 40),
              child: Text(
                statusMessage,
                style: GoogleFonts.montserrat(
                  fontSize: 14,
                  color: isSuccess ? Colors.green : Colors.black54,
                ),
                textAlign: TextAlign.center,
              ),
            ),
            const Spacer(),
            _buildFooter(context),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
      decoration: const BoxDecoration(
        color: Color(0xFF497CCE),
        borderRadius: BorderRadius.only(
          bottomLeft: Radius.circular(15),
          bottomRight: Radius.circular(15),
        ),
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              GestureDetector(
                onTap: () {
                  Navigator.pushReplacement(
                    context,
                    MaterialPageRoute(builder: (_) => const CreateAccountScreen()),
                  );
                },
                child: const Icon(Icons.arrow_back, color: Colors.white),
              ),
              const Icon(Icons.wifi, color: Colors.white),
              const Icon(Icons.menu, color: Colors.white),
            ],
          ),
          const SizedBox(height: 30),
          Text(
            'VERIFY YOUR EMAIL',
            style: GoogleFonts.montserrat(
              fontSize: 36,
              fontWeight: FontWeight.bold,
              color: Colors.white,
              letterSpacing: 1.5,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildFooter(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 14),
      decoration: const BoxDecoration(
        color: Color(0xFF497CCE),
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Center(
        child: TextButton(
          onPressed: () {
            Navigator.pushReplacement(
              context,
              MaterialPageRoute(builder: (_) => const LoginScreen()),
            );
          },
          child: Text(
            'Return to Login Page',
            style: GoogleFonts.montserrat(
              color: Colors.white,
              fontSize: 16,
            ),
          ),
        ),
      ),
    );
  }
}