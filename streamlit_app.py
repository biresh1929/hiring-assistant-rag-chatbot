import streamlit as st
from src.helper import (
    ConversationStage,
    generate_greeting,
    generate_technical_questions,
    check_exit_intent,
    generate_goodbye,
    handle_fallback
)
from src.context_manager import ConversationContextManager
from src.mongodb_handler import MongoDBHandler
from datetime import datetime
import uuid

st.markdown("""
<style>
    .consent-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: none;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        color: white;  /* ← Changed to white */
    }
    .consent-box h3 {
        color: white;
        font-weight: bold;
    }
    .consent-box ul li {
        color: #f0f0f0;  /* Slightly lighter white */
    }
    .info-box {
        background-color: #e8f5e9;  /* ← Light green instead of blue */
        border: 2px solid #4caf50;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
        color: #1b5e20;  /* Dark green text */
    }
</style>
""", unsafe_allow_html=True)

# Initialize MongoDB handler instead of DataHandler
if 'data_handler' not in st.session_state:
    st.session_state.data_handler = MongoDBHandler()

# Initialize in session state
if 'context_manager' not in st.session_state:
    st.session_state.context_manager = ConversationContextManager()

# When adding messages, also store in Pinecone
def add_message(role, content):
    """Add message to chat history and Pinecone"""
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    }
    st.session_state.messages.append(message)
    
    # Store in Pinecone
    if st.session_state.candidate_id:
        st.session_state.context_manager.store_conversation_turn(
            candidate_id=st.session_state.candidate_id,
            role=role,
            message=content,
            metadata={"stage": st.session_state.stage}
        )
    
    # Keep last 5 for immediate context
    st.session_state.conversation_context.append(f"{role}: {content}")
    if len(st.session_state.conversation_context) > 5:
        st.session_state.conversation_context.pop(0)

# Page configuration
st.set_page_config(
    page_title="TalentScout - Hiring Assistant",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 20px;
    }
    .chat-message {
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        animation: fadeIn 0.5s;
    }
    .user-message {
        background-color: #667eea;
        color: white;
        margin-left: 20%;
    }
    .assistant-message {
        background-color: #f0f0f0;
        color: #333;
        margin-right: 20%;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 10px;
        border-radius: 5px;
        font-weight: bold;
    }
    .success-box {
        background-color: #d4edda;
        border: 2px solid #28a745;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state variables
if 'initialized' not in st.session_state:
    st.session_state.initialized = False
    st.session_state.consent_given = False
    st.session_state.stage = ConversationStage.GREETING
    st.session_state.messages = []
    st.session_state.candidate_data = {
        "full_name": "",
        "email": "",
        "phone": "",
        "years_experience": "",
        "desired_position": "",
        "current_location": "",
        "tech_stack": [],
        "technical_questions": [],
        "answers": []
    }
    st.session_state.current_question_index = 0
    st.session_state.conversation_ended = False
    st.session_state.candidate_id = None
    st.session_state.conversation_context = []  # For context awareness

def display_messages():
    """Display chat messages with styling"""
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(
                f'<div class="chat-message user-message">👤 You: {message["content"]}</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'<div class="chat-message assistant-message">🤖 Assistant: {message["content"]}</div>',
                unsafe_allow_html=True
            )

def get_next_stage():
    """Move to next conversation stage"""
    stage_flow = [
        ConversationStage.GREETING,
        ConversationStage.COLLECTING_NAME,
        ConversationStage.COLLECTING_EMAIL,
        ConversationStage.COLLECTING_PHONE,
        ConversationStage.COLLECTING_EXPERIENCE,
        ConversationStage.COLLECTING_POSITION,
        ConversationStage.COLLECTING_LOCATION,
        ConversationStage.COLLECTING_TECH_STACK,
        ConversationStage.ASKING_QUESTIONS,
        ConversationStage.COMPLETED
    ]
    
    current_index = stage_flow.index(st.session_state.stage)
    if current_index < len(stage_flow) - 1:
        st.session_state.stage = stage_flow[current_index + 1]

def process_user_input(user_input):
    """Process user input with context awareness"""
    
    # Add user message
    add_message("user", user_input)
    
    # Check for exit intent
    if check_exit_intent(user_input):
        goodbye_msg = generate_goodbye(
            st.session_state.candidate_data.get("full_name", "there")
        )

        if st.session_state.candidate_data["full_name"]:
            candidate_id = st.session_state.candidate_id
            st.session_state.data_handler.save_candidate_data(
                candidate_id,
                st.session_state.candidate_data
            )

            goodbye_msg += f"\n\n✅ Your information has been saved securely.\n🔑 Your Candidate ID: **{candidate_id}**"
        
        add_message("assistant", goodbye_msg)
        st.session_state.conversation_ended = True
        return
    
    stage = st.session_state.stage
    
    # COLLECTING_NAME
    if stage == ConversationStage.COLLECTING_NAME:
        if len(user_input.split()) >= 1:
            st.session_state.candidate_data["full_name"] = user_input
            get_next_stage()
            response = f"Nice to meet you, {user_input}! 😊\n\nWhat's your email address?"
        else:
            response = "Please provide your full name so I can address you properly."
        add_message("assistant", response)
    
    # COLLECTING_EMAIL
    elif stage == ConversationStage.COLLECTING_EMAIL:
        if st.session_state.data_handler.validate_email(user_input):
            st.session_state.candidate_data["email"] = user_input
            get_next_stage()
            response = "Great! ✉️\n\nWhat's your phone number? (Include country code if applicable)"
        else:
            response = "That doesn't look like a valid email address. 🤔\n\nPlease provide a valid email (e.g., example@email.com)."
        add_message("assistant", response)
    
    # COLLECTING_PHONE
    elif stage == ConversationStage.COLLECTING_PHONE:
        if st.session_state.data_handler.validate_phone(user_input):
            st.session_state.candidate_data["phone"] = user_input
            get_next_stage()
            response = "Perfect! 📱\n\nHow many years of professional experience do you have?\n(Enter a number, e.g., 3, 5.5, or 0 if you're a fresher)"
        else:
            response = "Please provide a valid phone number (10-15 digits). You can include spaces or dashes."
        add_message("assistant", response)
    
    # COLLECTING_EXPERIENCE
    elif stage == ConversationStage.COLLECTING_EXPERIENCE:
        try:
            exp = ''.join(c for c in user_input if c.isdigit() or c == '.')
            if exp:
                st.session_state.candidate_data["years_experience"] = exp
                get_next_stage()
                response = "Excellent! 💼\n\nWhat position(s) are you interested in?\n(e.g., Software Engineer, Full Stack Developer, DevOps Engineer)"
            else:
                response = "Please provide your years of experience as a number (e.g., 3, 5.5, or 0 for fresher)."
        except:
            response = "Please provide a valid number for years of experience."
        add_message("assistant", response)
    
    # COLLECTING_POSITION
    elif stage == ConversationStage.COLLECTING_POSITION:
        if len(user_input) > 2:
            st.session_state.candidate_data["desired_position"] = user_input
            get_next_stage()
            response = "Got it! 🎯\n\nWhere are you currently located?\n(City, State/Country)"
        else:
            response = "Please provide the position(s) you're interested in."
        add_message("assistant", response)
    
    # COLLECTING_LOCATION
    elif stage == ConversationStage.COLLECTING_LOCATION:
        if len(user_input) > 2:
            st.session_state.candidate_data["current_location"] = user_input
            get_next_stage()
            response = "Thank you! 📍\n\n**Now, please list your tech stack:**\n"
            response += "Include programming languages, frameworks, databases, and tools you're proficient in.\n\n"
            response += "Examples:\n"
            response += "- Python, Django, PostgreSQL, Docker, AWS\n"
            response += "- JavaScript, React, Node.js, MongoDB, Git\n"
            response += "- Java, Spring Boot, MySQL, Kubernetes"
        else:
            response = "Please provide your current location."
        add_message("assistant", response)
    
    # COLLECTING_TECH_STACK
    elif stage == ConversationStage.COLLECTING_TECH_STACK:
        if len(user_input) > 3:
            # Parse tech stack
            tech_items = [
                item.strip() 
                for item in user_input.replace('\n', ',').replace(';', ',').split(',')
                if item.strip()
            ]
            
            st.session_state.candidate_data["tech_stack"] = tech_items
            
            # Generate technical questions based on tech stack
            with st.spinner("🤔 Generating technical questions tailored to your skills..."):
                questions = generate_technical_questions(
                    tech_stack=tech_items,
                    experience_years=st.session_state.candidate_data["years_experience"],
                    num_questions=5
                )
            
            st.session_state.candidate_data["technical_questions"] = questions
            st.session_state.current_question_index = 0
            get_next_stage()
            
            response = f"Perfect! 💻 I've noted your tech stack:\n**{', '.join(tech_items)}**\n\n"
            response += f"Now I'll ask you **{len(questions)} technical questions** tailored to your experience level ({st.session_state.candidate_data['years_experience']} years).\n\n"
            response += "Take your time to answer each question thoroughly.\n\n"
            response += f"**Question 1/{len(questions)}:**\n{questions[0]}"
            
            add_message("assistant", response)
        else:
            response = "Please provide your tech stack. List the technologies, languages, frameworks, and tools you work with."
            add_message("assistant", response)
    
    # ASKING_QUESTIONS
    elif stage == ConversationStage.ASKING_QUESTIONS:
        questions = st.session_state.candidate_data["technical_questions"]
        current_idx = st.session_state.current_question_index
        
        # Save the answer
        st.session_state.candidate_data["answers"].append({
            "question": questions[current_idx],
            "answer": user_input
        })
        
        # Move to next question
        st.session_state.current_question_index += 1
        
        # Check if all questions answered
        if st.session_state.current_question_index >= len(questions):
            st.session_state.stage = ConversationStage.COMPLETED
            response = "✅ Thank you for answering all the questions!\n\nThat completes our initial screening. Let me save your information..."
            add_message("assistant", response)
            
            # Save candidate data
            candidate_id = st.session_state.candidate_id
            st.session_state.data_handler.save_candidate_data(
                candidate_id,
                st.session_state.candidate_data
            )

            st.session_state.conversation_ended = True
            
            final_msg = f"\n\n**🎉 Screening Complete!**\n\n"
            final_msg += f"🔑 **Your Candidate ID:** `{candidate_id}`\n\n"
            final_msg += "Your responses have been saved securely with encryption.\n\n"
            final_msg += "**Next Steps:**\n"
            final_msg += "- Our recruitment team will review your profile\n"
            final_msg += "- We'll contact you within 3-5 business days\n"
            final_msg += "- Save your Candidate ID to access/manage your data\n\n"
            final_msg += "**Your GDPR Rights:**\n"
            final_msg += "- 📄 Access your data\n"
            final_msg += "- ✏️ Update your information\n"
            final_msg += "- 🗑️ Request data deletion\n"
            final_msg += "- 📤 Export your data"
            
            add_message("assistant", final_msg)
        else:
            next_question = questions[st.session_state.current_question_index]
            response = f"Thank you for your answer! 👍\n\n**Question {st.session_state.current_question_index + 1}/{len(questions)}:**\n{next_question}"
            add_message("assistant", response)
    
    # Fallback
    else:
        response = handle_fallback(user_input, stage)
        add_message("assistant", response)

# Main App
def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🎯 TalentScout Hiring Assistant</h1>
        <p>AI-Powered Initial Candidate Screening | GDPR Compliant</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("ℹ️ Information")
        
        st.markdown("""
        **About This Chatbot:**
        - Initial candidate screening
        - Tech stack-based questions
        - GDPR compliant
        - Secure data encryption
        
        **Process:**
        1. Provide basic information
        2. List your tech stack
        3. Answer technical questions
        4. Get your Candidate ID
        """)
        
        st.markdown("---")
        
        st.markdown("**🔒 Privacy & Security**")
        if st.button("View Privacy Policy"):
            st.markdown("""
            ✅ Data encrypted with Fernet  
            ✅ GDPR compliant  
            ✅ 365-day retention  
            ✅ Right to erasure  
            """)
        
        st.markdown("---")
        
        if st.session_state.candidate_id:
            st.success(f"**Your ID:**\n`{st.session_state.candidate_id}`")
        
        # Reset button
        if st.button("🔄 Start New Conversation"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    # GDPR Consent
    if not st.session_state.consent_given:
        st.markdown("""
        <div class="consent-box">
            <h3>🔒 Privacy & Data Protection Notice</h3>
            <p>By continuing, you consent to TalentScout collecting and processing your personal data for initial candidate screening purposes.</p>
            <p><strong>We collect:</strong> Name, Email, Phone, Experience, Position, Location, Tech Stack, Interview Responses</p>
            <p><strong>Your data is:</strong></p>
            <ul>
                <li>✅ Encrypted with industry-standard encryption</li>
                <li>✅ Stored securely for 12 months</li>
                <li>✅ Protected under GDPR regulations</li>
                <li>✅ Never sold to third parties</li>
            </ul>
            <p><strong>Your rights:</strong> Access, Rectification, Erasure, Portability</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ I Understand and Accept", key="accept_consent"):

                st.session_state.candidate_id = f"candidate_{uuid.uuid4().hex}"
                st.session_state.consent_given = True
                st.session_state.initialized = True
                
                # Generate greeting
                greeting = generate_greeting()
                add_message("assistant", greeting)
                add_message("assistant", "Let's start with your full name. What should I call you?")
                get_next_stage()
                st.rerun()
        
        with col2:
            if st.button("❌ Decline"):
                st.error("You must accept the privacy policy to use this service.")
                st.stop()
    
    else:
        # Display conversation
        display_messages()
        
        # Input area
        if not st.session_state.conversation_ended:
            st.markdown("---")
            
            user_input = st.text_area(
                "Your response:",
                key="user_input",
                height=100,
                placeholder="Type your response here..."
            )
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                if st.button("📤 Send", key="send_button", use_container_width=True):
                    if user_input.strip():
                        process_user_input(user_input.strip())
                        st.rerun()
                    else:
                        st.warning("Please enter a response before sending.")
            
            with col2:
                if st.button("🚪 Exit", key="exit_button", use_container_width=True):
                    process_user_input("exit")
                    st.rerun()
            
            # Show context awareness indicator
            st.markdown("---")
            with st.expander("🧠 Conversation Context (AI Awareness)"):
                st.markdown("**Recent Context:**")
                for ctx in st.session_state.conversation_context[-3:]:
                    st.text(ctx)
        
        else:
            st.markdown("""
            <div class="success-box">
                <h3>✅ Conversation Completed</h3>
                <p>Thank you for using TalentScout Hiring Assistant!</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("---")
            st.subheader("🔐 Your Data & Privacy Rights (GDPR)")

            handler = st.session_state.data_handler
            candidate_id = st.session_state.candidate_id

            col1, col2 = st.columns(2)

            with col1:
                if st.button("📄 View My Data"):
                    data = handler.get_candidate_data(candidate_id)
                    if data:
                        st.json(data)
                    else:
                        st.warning("No data found.")

                if st.button("⬇️ Download My Data (JSON)"):
                    exported = handler.export_candidate_data(candidate_id, "json")
                    if exported:
                        st.download_button(
                            label="Download JSON",
                            data=exported,
                            file_name=f"{candidate_id}_data.json",
                            mime="application/json"
                        )

            with col2:
                if st.button("🗑️ Delete My Data (Permanent)"):
                    deleted = handler.delete_candidate_data(candidate_id)
                    if deleted:
                        st.success("✅ Your data has been permanently deleted.")
                        st.warning("This session will now end.")
                        st.session_state.clear()
                        st.stop()



            if st.button("🔄 Start New Screening"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

if __name__ == "__main__":
    main()