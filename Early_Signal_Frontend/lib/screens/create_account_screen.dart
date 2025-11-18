import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_functions/cloud_functions.dart';

import 'login_screen.dart';
import 'package:firebase_core/firebase_core.dart';

class CreateAccountScreen extends StatefulWidget {
  const CreateAccountScreen({super.key});

  @override
  State<CreateAccountScreen> createState() => _CreateAccountScreenState();
}

class _CreateAccountScreenState extends State<CreateAccountScreen> {
  bool isChecked = false;
  final _formKey = GlobalKey<FormState>();

  final _emailController = TextEditingController();
  final _usernameController = TextEditingController();
  final _nameController = TextEditingController();
  final _mobileController = TextEditingController();
  final _passwordController = TextEditingController();
  final _repeatPasswordController = TextEditingController();

  bool _showPassword = false;
  bool _showRepeatPassword = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey[200],
      body: SafeArea(
        child: SingleChildScrollView(
          child: ConstrainedBox(
            constraints: BoxConstraints(minHeight: MediaQuery
                .of(context)
                .size
                .height),
            child: IntrinsicHeight(
              child: Column(
                children: [
                  _buildHeader(),
                  const SizedBox(height: 28),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    child: Form(
                      key: _formKey,
                      child: Column(
                        children: [
                          _buildField(
                            hint: "Mobile number (e.g. +1 123 456 7890) *",
                            controller: _mobileController,
                            validator: (val) =>
                            val == null || val.isEmpty
                                ? 'Enter mobile number'
                                : null,
                          ),
                          const SizedBox(height: 30),
                          _buildField(
                            hint: "Email Address *",
                            controller: _emailController,
                            validator: (val) =>
                            val != null && val.contains('@')
                                ? null
                                : 'Enter valid email',
                          ),
                          const SizedBox(height: 30),
                          _buildField(
                            hint: "Name *",
                            controller: _nameController,
                            validator: (val) =>
                            val == null || val.isEmpty ? 'Enter name' : null,
                          ),
                          const SizedBox(height: 30),
                          _buildField(
                            hint: "Username *",
                            controller: _usernameController,
                            validator: (val) =>
                            val == null || val.isEmpty
                                ? 'Enter username'
                                : null,
                          ),
                          const SizedBox(height: 30),
                          _buildField(
                            hint: "Password *",
                            controller: _passwordController,
                            isPassword: true,
                            validator: (val) =>
                            val != null && val.length >= 6
                                ? null
                                : 'Minimum 6 characters',
                          ),
                          const SizedBox(height: 30),
                          _buildField(
                            hint: "Repeat Password *",
                            controller: _repeatPasswordController,
                            isPassword: true,
                            validator: (val) =>
                            val == _passwordController.text
                                ? null
                                : 'Passwords do not match',
                          ),
                          const SizedBox(height: 30),
                          Text(
                            "Before we begin, we just ask that you share info in good faith to help keep our community healthy.",
                            textAlign: TextAlign.center,
                            style: GoogleFonts.montserrat(),
                          ),
                          const SizedBox(height: 12),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Checkbox(
                                value: isChecked,
                                onChanged: (value) =>
                                    setState(() => isChecked = value!),
                                activeColor: const Color(0xFF497CCE),
                              ),
                              Text("I understand and agree",
                                  style: GoogleFonts.montserrat()),
                            ],
                          ),
                          const SizedBox(height: 12),
                          ElevatedButton(
                            onPressed: isChecked &&
                                _formKey.currentState!.validate()
                                ? _handleSignUp
                                : null,
                            style: ElevatedButton.styleFrom(
                              minimumSize: const Size(double.infinity, 50),
                              backgroundColor: const Color(0xFF497CCE),
                              shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(30)),
                            ),
                            child: Text(
                              "Create Account",
                              style: GoogleFonts.montserrat(
                                fontWeight: FontWeight.bold,
                                fontSize: 16,
                                color: Colors.white,
                              ),
                            ),
                          ),
                          const SizedBox(height: 30),
                        ],
                      ),
                    ),
                  )
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildField({
    required String hint,
    bool isPassword = false,
    TextEditingController? controller,
    String? Function(String?)? validator,
  }) {
    bool isRepeat = hint.toLowerCase().contains("repeat");

    return TextFormField(
      controller: controller,
      obscureText: isPassword
          ? !(isRepeat ? _showRepeatPassword : _showPassword)
          : false,
      validator: validator,
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: GoogleFonts.montserrat(),
        suffixIcon: isPassword
            ? IconButton(
          icon: Icon(
            (isRepeat ? _showRepeatPassword : _showPassword)
                ? Icons.visibility
                : Icons.visibility_off,
          ),
          onPressed: () {
            setState(() {
              if (isRepeat) {
                _showRepeatPassword = !_showRepeatPassword;
              } else {
                _showPassword = !_showPassword;
              }
            });
          },
        )
            : null,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(30)),
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      width: double.infinity,
      padding:
      const EdgeInsets.only(top: 30, left: 16, right: 16, bottom: 30),
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
                onTap: () => Navigator.pop(context),
                child: const Icon(Icons.arrow_back, color: Colors.white),
              ),
              const Icon(Icons.wifi, color: Colors.white),
              const Icon(Icons.menu, color: Colors.white),
            ],
          ),
          const SizedBox(height: 30),
          Text(
            "CREATE YOUR ACCOUNT",
            style: GoogleFonts.montserrat(
              fontSize: 36,
              fontWeight: FontWeight.bold,
              color: Colors.white,
              letterSpacing: 1.2,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Future<void> _handleSignUp() async {
    final email = _emailController.text.trim();
    final password = _passwordController.text.trim();

    try {
      // Step 1: Create account
      final userCredential = await FirebaseAuth.instance
          .createUserWithEmailAndPassword(email: email, password: password);

      // Step 2: Wait until user is fully authenticated
      await FirebaseAuth.instance.currentUser?.reload();
      final user = FirebaseAuth.instance.currentUser;
      if (user == null) {
        throw Exception("User not available after creation");
      }

      // Step 3: Force refresh ID token
      await user.getIdToken(true);

      // Step 4: Configure functions instance for emulator with region and project ID
      final functions = FirebaseFunctions.instanceFor(
        app: Firebase.app(),
        region: 'us-central1',
      );
      functions.useFunctionsEmulator('10.0.2.2', 5001); // For Android emulator

      // Step 5: Call the Cloud Function
      final callable = functions.httpsCallable('createUserRecord');

      final result = await callable.call(<String, dynamic>{
        'user_id': user.uid,
        'email': email,
        'username': _usernameController.text.trim(),
        'name': _nameController.text.trim(),
        'mobile_number': _mobileController.text.trim(),
      });

      final Map<String, dynamic> data = Map<String, dynamic>.from(result.data);

      if (data['success'] == true) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (_) => const LoginScreen()),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Signup worked, but BigQuery failed.")),
        );
      }
    } on FirebaseAuthException catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Signup failed: ${e.message}")),
      );
    } catch (e, stackTrace) {
      debugPrint("🔥 Unexpected error during signup:");
      debugPrint("Type: ${e.runtimeType}");
      debugPrint("Error: $e");
      debugPrint("Stack trace: $stackTrace");

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Error: $e")),
      );
    }
  }
}
