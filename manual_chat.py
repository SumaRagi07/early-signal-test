"""
Manual chat interface for the LangGraph health chatbot.
Run this script and type your responses to have a conversation.
"""

import sys
from graph_orchestrator import run_graph_chat_flow
import uuid

def print_separator():
    print("\n" + "="*70 + "\n")

def manual_chat():
    """Interactive chat session with the health chatbot"""
    
    print("""
    ╔════════════════════════════════════════════════════════════════════╗
    ║            HEALTH CHATBOT - MANUAL CONVERSATION MODE               ║
    ╚════════════════════════════════════════════════════════════════════╝
    
    This chatbot will help you report your symptoms and track potential
    disease exposure for public health purposes.
    
    Commands:
    - Type your responses naturally
    - Type 'quit' or 'exit' to end the conversation
    - Type 'restart' to start a new session
    - Type 'status' to see your current data
    
    """)
    
    # Generate a unique session ID for this conversation
    session_id = f"manual_{uuid.uuid4().hex[:8]}"
    print(f"Session ID: {session_id}")
    print_separator()
    
    # Start the conversation
    print("BOT: Hello! I'm here to help you report your symptoms.")
    print("     Please describe any symptoms you're experiencing.")
    print_separator()
    
    conversation_count = 0
    
    while True:
        # Get user input
        try:
            user_input = input("YOU: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nGoodbye!")
            break
        
        if not user_input:
            print("(Please type something or 'quit' to exit)")
            continue
        
        # Handle special commands
        if user_input.lower() in ['quit', 'exit', 'bye']:
            print("\nThank you for using the health chatbot. Take care!")
            break
        
        if user_input.lower() == 'restart':
            print("\n🔄 Starting new session...\n")
            session_id = f"manual_{uuid.uuid4().hex[:8]}"
            print(f"New Session ID: {session_id}")
            print_separator()
            print("BOT: Hello! I'm here to help you report your symptoms.")
            print("     Please describe any symptoms you're experiencing.")
            print_separator()
            conversation_count = 0
            continue
        
        if user_input.lower() == 'status':
            print("\n📊 Current Session Status:")
            print(f"   Session ID: {session_id}")
            print(f"   Messages exchanged: {conversation_count}")
            print_separator()
            continue
        
        # Process the user input through the chatbot
        try:
            result, history = run_graph_chat_flow(user_input, session_id)
            conversation_count += 1
            
            # Display the bot's response
            print_separator()
            print(f"BOT: {result['console_output']}")
            
            # Show diagnosis if available
            if result.get('diagnosis') and result['diagnosis'].get('final_diagnosis'):
                diagnosis = result['diagnosis']
                print(f"\n     📋 Diagnosis: {diagnosis['final_diagnosis']}")
                print(f"     Category: {diagnosis.get('illness_category', 'N/A')}")
                print(f"     Confidence: {diagnosis.get('confidence', 0):.0%}")
            
            # Show if report was submitted
            if result.get('report'):
                report = result['report']
                print(f"\n     ✅ Report #{report.get('report_id')} submitted to database")
                print(f"     Exposure: {report.get('exposure_location_name', 'N/A')}")
                print(f"     Location: {report.get('current_location_name', 'N/A')}")
            
            # Show care advice if provided
            if result.get('care_advice'):
                care = result['care_advice']
                print("\n     💊 Care Advice Provided:")
                for i, tip in enumerate(care.get('self_care_tips', [])[:3], 1):
                    print(f"        {i}. {tip}")
                if len(care.get('self_care_tips', [])) > 3:
                    print(f"        ... and {len(care['self_care_tips']) - 3} more tips")
            
            print_separator()
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Please try again or type 'restart' for a new session.")
            print_separator()
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    try:
        manual_chat()
    except KeyboardInterrupt:
        print("\n\nConversation ended. Goodbye!")
        sys.exit(0)