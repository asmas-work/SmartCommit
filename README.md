# SmartCommit

SmartCommit is an AI-powered web application that helps developers generate meaningful commit messages for their code changes using GPT.

## Features

- Automatically detects unstaged changes in your Git repository
- Uses GPT to generate clear and concise commit messages
- Provides a user-friendly interface through Streamlit
- Allows direct committing of changes with the generated message

## Prerequisites

- Python 3.8 or higher
- Git
- OpenAI API key

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/SmartCommit.git
cd SmartCommit
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root and add your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

## Usage

1. Run the Streamlit application:
```bash
streamlit run app.py
```

2. Open your web browser and navigate to the URL shown in the terminal (usually http://localhost:8501)

3. In the sidebar:
   - Enter the path to your Git repository
   - Provide your OpenAI API key if not set in the .env file

4. The application will:
   - Show any unstaged changes in your repository
   - Generate a commit message using GPT
   - Allow you to commit the changes with the generated message

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 