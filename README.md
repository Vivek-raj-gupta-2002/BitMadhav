
 # BitMadhav

 BitMadhav is an AI-powered assistant designed for restaurants to streamline table reservations and customer inquiries. It leverages Django Channels for real-time audio communication with Twilio and integrates Azure OpenAI for transcription and natural language processing. BitMadhav is capable of handling voice and text inputs, validating reservations against business rules, and providing dynamic responses in multiple languages (including Hinglish).

 ## Features

 - **Real-Time Audio Communication:**  
   Uses Django Channels to manage live WebSocket connections between Twilio and the OpenAI API.

 - **AI-Powered Transcription ^& Extraction:**  
   Integrates Azure OpenAI to transcribe incoming audio and extract key reservation details (e.g., customer name, guest count, reservation date ^& time, phone number).

 - **Reservation Validation:**  
   Enforces business rules such as:
   - Accepting reservations only between 5:00 PM and 9:00 PM.
   - Allowing bookings for today or tomorrow only.
   - Preventing overlapping reservations within a defined time window.


 - **Comprehensive Reservation Management:**  
   Persists reservation data in a Django model and allows for future enhancements like modification, cancellation, waitlisting, and analytics.

 - **Voice Response Configuration:**  
   Uses a configured voice (e.g., Alloy) for generating audio responses.

 ## Getting Started

 ### Prerequisites

 - Python 3.8+
 - Django 3.2+ (or Django 4.x)
 - Redis (for Celery broker)
 - Celery
 - Django Channels
 - Twilio Account (for audio integration)
 - Azure OpenAI Service (with valid API keys and endpoint)
 - Other dependencies as listed in `requirements.txt`

 ### Installation

 1. **Clone the repository:**

    git clone https://github.com/yourusername/bitmadhav.git
    cd bitmadhav

 2. **Create and activate a virtual environment:**

    python -m venv venv
    venv\Scripts\activate

 3. **Install dependencies:**

    pip install -r requirements.txt

 4. **Set up environment variables:**  
    Create a `.env` file (or configure your environment) with the following keys:

    # Azure OpenAI settings
    OPENAI_API_KEY=your_azure_openai_api_key
    
    ENDPOINT=wss://your-resource-name.openai.azure.com

    AZURE_ENDPOINT=https://your-resource-name.openai.azure.com
    

    # Twilio settings
    TWILIO_SID=your_twilio_account_sid

    TWILIO_AUTH_TOKEN=your_twilio_auth_token
    
    TWILIO_NUMBER=your_twilio_number


 6. **Apply migrations:**

    python manage.py migrate


 7. **Run Django development server:**

    python manage.py runserver

 ## Project Structure

 bitmadhav/
 
 ├── AgentApp/                  # Django app containing business logic, models, and consumers
 
 │   ├── consumers.py          # WebSocket consumer for real-time communication
 
 │   ├── models.py             # Django models (e.g., Table, Sid)
 
 │   └── ...
 
 ├── bitmadhav/                # Project settings and configuration
 
 │   ├── settings.py
 
 │   ├── urls.py
 
 │   └── ...
 
 ├── requirements.txt          # Python dependencies
 
 ├── manage.py                 # Django management script
 
 └── README.md                 # This file

 ## Running the Project

 1. **Start the Django Server:**  

    python manage.py runserver

 2. **Connect with Twilio:**  
    Configure your Twilio webhook URL to point to your WebSocket endpoint (e.g., https://<host>/api/incoming-call).

 ## Customization ^& Enhancements

 - **Reservation Logic:**  
   Customize the business rules in `consumers.py` to adjust reservation times, overlaps, or other criteria.

 - **AI Integration:**  
   Update the Azure OpenAI API version and deployment model as needed. Adjust system prompts and function parameters to fine-tune the AI’s behavior.

 - **User Interface:**  
   Consider developing a front-end dashboard for staff to manage reservations and monitor system analytics.

 - **Error Handling ^& Logging:**  
   Implement comprehensive logging and error handling to improve debugging and reliability.

 ## Contributing

 Contributions are welcome! Please fork the repository and submit a pull request with your improvements. For major changes, open an issue first to discuss your ideas.


 ## Contact

 For questions or support, please contact [vivekrajgupta2002@outlook.com](mailto:vivekrajgupta2002@outlook.com).

