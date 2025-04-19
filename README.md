Game Tester Dashboard
=====================

Overview
--------

The **Game Tester Dashboard** is a Python-based web application built with Streamlit, designed to assist game developers and testers in evaluating game performance, tracking bugs, and analyzing player satisfaction. It generates mock test reports for a predefined list of over 700 popular video games, providing detailed analytics through interactive visualizations. The application includes an AI-powered chatbot, integrated with the Google Gemini API, which offers real-time assistance and supports file uploads (images and text) for analysis. With a sleek, user-friendly interface styled using custom CSS, the dashboard is an effective tool for optimizing game development and testing workflows.

Features
--------

*   **Game Selection**: Choose from a curated list of over 700 video games for test report generation.
    
*   **Mock Test Reports**: Generate comprehensive reports including:
    
    *   Performance metrics (FPS, CPU/GPU usage, memory usage).
        
    *   Bug tracking (categorized by type, severity, and area with detailed descriptions).
        
    *   Gameplay statistics (playtime, completion rate, player deaths, achievements).
        
    *   User satisfaction scores and platform-specific performance.
        
*   **Interactive Visualizations**:
    
    *   FPS distribution histogram.
        
    *   Resource utilization bar chart.
        
    *   Performance-over-time line chart.
        
    *   Bug distribution pie chart and severity bar chart.
        
    *   Platform performance comparison bar chart.
        
*   **AI-Powered Chatbot**:
    
    *   Real-time assistance using the Google Gemini API.
        
    *   Supports text queries and file uploads (images, text, CSV, JSON, etc.).
        
    *   Contextual responses based on test results and chat history.
        
*   **File Upload Support**:
    
    *   Upload images for visual analysis with preview.
        
    *   Upload text-based files (e.g., logs, scripts) for content analysis.
        
*   **Customizable UI**:
    
    *   Collapsible API key configuration and chatbot interface.
        
    *   Custom CSS for enhanced aesthetics (report cards, hover effects, chat styling).
        
    *   Progress bar for loading states and error handling for invalid inputs.
        
*   **Recommendations**: Personalized suggestions for game optimization based on test results.
    

Prerequisites
-------------

*   **Python 3.8+**: Ensure Python is installed on your system.
    
*   **Google Gemini API Key**: Obtain an API key from [Google AI Studio](https://ai.google.dev/).
    

Installation
------------

1.  ```bash
    git clone https://github.com/hariteja-01/Game-Tester-Using-AI.gitcd Game-Tester-Using-AI
    ```
    
2.  ```bash
    python -m venv venvsource venv/bin/activate # On Windows: venv\\Scripts\\activate
    ```
    
3.  ```bash
    pip install -r requirements.txtThe requirements.txt
    should include:
    streamlit==1.38.0
    google-generativeai==0.7.2
    plotly==5.24.1
    pandas==2.2.3
    pillow==10.4.0
    ```
    
4.  **Configure the Gemini API Key**:
    
    *   DEFAULT\_API\_KEY = "your-gemini-api-key"
        
    *   Alternatively, input the API key through the dashboard's UI during runtime.
        

Usage
-----

1.  ```bash
    streamlit run AICA3_S1.py
    ```
    
2.  **Access the Dashboard**:
    
    *   Open your browser and navigate to http://localhost:8501.
        
    *   The dashboard will load with a game selection form and API key configuration section.
        
3.  **Generate a Test Report**:
    
    *   Select a game from the dropdown menu (e.g., "Minecraft", "Elden Ring").
        
    *   Click "Generate Test Report" to create a mock test report with visualizations and bug details.
        
4.  **Interact with the Chatbot**:
    
    *   Click the chat icon (💬) in the bottom-right corner to open the chatbot.
        
    *   Type queries or upload files (images or text) for analysis.
        
    *   The chatbot provides contextual responses based on test results or uploaded content.
        
5.  **Explore Visualizations and Recommendations**:
    
    *   View performance charts, bug distributions, and platform comparisons.
        
    *   Review the detailed bug list and personalized recommendations for game optimization.

Technologies Used
-----------------

*   **Programming Languages**: Python, HTML/CSS (for Streamlit styling)
    
*   **Libraries and Frameworks**:
    
    *   Streamlit: Web application framework
        
    *   google-generativeai: Google Gemini API integration
        
    *   Plotly: Interactive visualizations
        
    *   Pandas: Data manipulation
        
    *   Pillow: Image processing
        
*   **Other Tools**:
    
    *   Google Gemini API: AI-powered chatbot
        
    *   GitHub: Version control
        
    *   Streamlit Community Cloud: Optional deployment platform
        

Deployment
----------

To deploy the application on **Streamlit Community Cloud**:

1.  Push the repository to GitHub.
    
2.  Sign in to [Streamlit Community Cloud](https://share.streamlit.io/).
    
3.  Create a new app, linking it to your GitHub repository.
    
4.  Specify AICA3_S1.py as the main script.
    
5.  Add the Gemini API key as a secret in the app settings.
    
6.  Deploy the app and access it via the provided URL.
    

Future Enhancements
-------------------

*   Integrate real test data from game testing frameworks.
    
*   Add support for user-defined games or external game APIs.
    
*   Implement user authentication and report export (PDF/CSV).
    
*   Enhance chatbot with advanced NLP or multi-model AI support.
    
*   Add multi-language support for global accessibility.
    
*   Enable real-time collaboration for team-based testing.
    

Troubleshooting
---------------

*   **Gemini API Key Error**: Ensure the API key is valid and has access to the gemini-1.5-flash model. Check [Google AI Studio](https://ai.google.dev/) for key generation.
    
*   **Module Not Found**: Verify all dependencies are installed (pip install -r requirements.txt).
    
*   **Invalid Game Name**: Select a game from the provided dropdown list, as only predefined games are supported.
    
*   **Chatbot Not Responding**: Check internet connectivity and API key configuration.
    

License
-------

This project is licensed under the MIT License. See the [LICENSE](https://github.com/hariteja-01/Game-Tester-Using-AI/blob/main/LICENSE) file for details.

Contact
-------

For questions or contributions, please contact \[[Click here!](mailto:patnalahariteja@gmail.com)\] or open an issue on the [GitHub Repository Issues](https://github.com/hariteja-01/Game-Tester-Using-AI/issues).
