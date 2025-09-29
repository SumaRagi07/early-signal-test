# app.py
import streamlit as st
import json
from datetime import datetime
from helpers import strip_fences, generate, compute_days_ago, fix_json, normalize_agent_response, get_input, parse_json_from_response
from config import PROJECT_ID, LOCATION, MODEL, PINECONE_INDEX_NAME, TABLE_ID
from agents.symptom_agent import run_agent as run_symptom
from agents.exposure_agent import run_agent as run_exposure
from agents.diagnostic_agent import run_agent as run_diagnostic
from agents.location_agent import run_agent as run_location
from agents.bq_submitter_agent import run_agent as run_bq
from agents.care_agent import run_agent as run_care

# Global counter for reports (for demonstration purposes, not persistent)
if 'REPORT_COUNTER' not in st.session_state:
    st.session_state.REPORT_COUNTER = 0

def check_environment():
    required = [PROJECT_ID, PINECONE_INDEX_NAME, TABLE_ID]
    if not all(required):
        st.error("❌ Missing environment configurations! Please check your `config.py` file.")
        return False
    return True

def app_main():
    st.set_page_config(page_title="EarlySignal Chat", page_icon="👋")
    st.title("👋 Welcome to EarlySignal Chat")
    st.markdown("Tell me your symptoms and when they began (days ago).")

    if not check_environment():
        return

    # Initialize chat history in session state
    if "history" not in st.session_state:
        st.session_state.history = []

    # Display chat messages from history on app rerun
    for message in st.session_state.history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept user input
    user_input = st.chat_input("Tell me your symptoms and when they began (e.g., 'fever and cough for 3 days')")

    if user_input:
        # Add user message to chat history
        st.session_state.history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        try:
            # Symptom Agent
            with st.spinner("Analyzing symptoms..."):
                sym_json, st.session_state.history = run_symptom(user_input, st.session_state.history)
                sym = normalize_agent_response(sym_json, "symptom")
                symptoms = sym.get("symptoms", [])
                onset = sym.get("days_since_onset")

            if not symptoms:
                st.warning("⚠️ No symptoms detected. Please try again.")
                return

            # Diagnostic Agent (merged clarifier + diagnoser)
            with st.spinner("Running diagnostic analysis..."):
                diag_json, st.session_state.history = run_diagnostic(
                    json.dumps({"symptoms": symptoms, "days_since_onset": onset}),
                    st.session_state.history
                )
                diag = parse_json_from_response(diag_json)

            if diag.get("final_diagnosis") == "Unknown (insufficient data)":
                st.info("🔍 Couldn't determine a clear diagnosis - please consult a doctor")
                return

            if diag.get("confidence", 0) < 0.5:
                st.warning("⚠️ Low confidence diagnosis - consider human review")

            st.markdown(f"\n🔬 **Most Likely Diagnosis:** {diag['final_diagnosis']}")
            st.markdown(f"**Category:** {diag['illness_category']}")
            st.markdown(f"**Confidence:** {diag['confidence']:.0%}")
            st.markdown(f"**Reasoning:** {diag['reasoning']}")

            # Exposure Phase
            with st.spinner("Gathering exposure information..."):
                exp_payload = {
                    "illness_category": diag["illness_category"],
                    "diagnosis": diag["final_diagnosis"],
                    "symptom_summary": ", ".join(symptoms),
                    "days_since_exposure": onset
                }
                exp_json, st.session_state.history = run_exposure(json.dumps(exp_payload), st.session_state.history)
                exp = json.loads(exp_json)

            # Location Agent
            with st.spinner("Determining current location..."):
                loc_json, st.session_state.history = run_location(user_input, st.session_state.history)
                loc = json.loads(loc_json)

            # Assemble and submit the single flat report
            st.session_state.REPORT_COUNTER += 1
            report = {
                "report_id": st.session_state.REPORT_COUNTER,
                "user_id": 1,  # Placeholder, consider dynamic user ID
                "report_timestamp": datetime.utcnow().isoformat() + "Z",
                "symptom_text": ", ".join(symptoms),
                "days_since_symptom_onset": onset,
                "final_diagnosis": diag["final_diagnosis"],
                "illness_category": diag["illness_category"],
                "confidence": diag["confidence"],
                "reasoning": diag.get("reasoning"),
                "exposure_location_name": exp.get("exposure_location_name"),
                "exposure_latitude": exp.get("exposure_latitude"),
                "exposure_longitude": exp.get("exposure_longitude"),
                "days_since_exposure": exp.get("days_since_exposure"),
                "current_location_name": loc.get("current_location_name"),
                "current_latitude": loc.get("current_latitude"),
                "current_longitude": loc.get("current_longitude"),
                "restaurant_visit": False,  # TO FIX LATER
                "outdoor_activity": False,  # TO FIX LATER
                "water_exposure": False,  # TO FIX LATER
                "location_category": loc.get("location_category"),
                "contagious_flag": diag["illness_category"] == "airborne",
                "alertable_flag": diag["illness_category"] in ["airborne", "waterborne", "insect-borne", "foodborne"],
            }

            st.markdown("---")
            st.subheader("📋 Case Summary:")
            st.markdown(f"🩺 **Most Likely Diagnosis:** {report['final_diagnosis']} ({report['confidence']:.0%} confidence)")
            st.markdown(f"📍 **Probable Exposure:** {report['exposure_location_name']} ({report['days_since_exposure']} days ago)")
            st.markdown(f"🏠 **Current Location:** {report['current_location_name']}")
            if report["alertable_flag"]:
                st.warning("⚠️ **Public Health Alert:** This case meets notification criteria")

            # BigQuery Submission Phase
            with st.spinner("Submitting report..."):
                result_json, st.session_state.history = run_bq(json.dumps(report), st.session_state.history)
                result = json.loads(result_json)

            if result.get("status") == "success":
                st.success("✅ Report successfully submitted.")
            else:
                st.error(f"❌ Submission error: {result.get('message')}")

            # Self Care Agent
            with st.spinner("Generating self-care tips..."):
                care_str, st.session_state.history = run_care(json.dumps(report), st.session_state.history)
                try:
                    care = parse_json_from_response(care_str)
                except Exception as e:
                    st.error(f"❌ Failed to parse self-care JSON: {e}")
                    care = {}

            st.subheader("🤖 Self-Care Tips")
            if care.get("self_care_tips"):
                for tip in care.get("self_care_tips", []):
                    st.markdown(f" • {tip}")
            else:
                st.info("No specific self-care tips available at this moment.")

            st.markdown(f"**When to seek medical attention:**\n {care.get('when_to_seek_help', 'Please consult a medical professional if your symptoms worsen or persist.')}\n")

            st.success("👋 Thank you for using EarlySignal and helping the community stay healthy — take care!")
            st.session_state.history.append({"role": "assistant", "content": "Thank you for using EarlySignal! If you have more symptoms to report, please refresh the page."})


        except Exception as e:
            st.error(f"⚠️ An unexpected error occurred: {str(e)}")

if __name__ == "__main__":
    app_main()