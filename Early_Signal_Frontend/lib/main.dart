import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'firebase_options.dart';
import 'package:provider/provider.dart'; // Add this import
import 'package:cloud_functions/cloud_functions.dart';

import 'services/app_state.dart'; // Add this import
import 'screens/login_screen.dart';
import 'screens/create_account_screen.dart';
import 'screens/verify_email_screen.dart';
import 'screens/reset_password.dart';
import 'screens/home_screen.dart';
import 'screens/outbreak_dashboard.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );

  // Uncomment below if you're using Firebase Cloud Functions locally
  /*
  FirebaseFunctions functions = FirebaseFunctions.instanceFor(region: 'us-central1');
  functions.useFunctionsEmulator('10.0.2.2', 5001);
  */

  runApp(
    MultiProvider( // Changed from single Provider to MultiProvider for future expansion
      providers: [
        ChangeNotifierProvider(create: (_) => AppState()),
        // Add other providers here if needed later
      ],
      child: const MyApp(),
    ),
  );
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'EarlySignal',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue),
        useMaterial3: true,
      ),
      initialRoute: '/login',
      routes: {
        '/login': (context) => const LoginScreen(),
        '/create-account': (context) => const CreateAccountScreen(),
        '/reset-password': (context) => const ResetPasswordScreen(),
        '/home': (context) => const HomeScreen(),
        '/dashboard': (context) => const OutbreakDashboardPage(),
      },
    );
  }
}