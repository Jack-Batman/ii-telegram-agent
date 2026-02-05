#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Banner
print_banner() {
    echo -e "${PURPLE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║     ██╗██╗    ████████╗███████╗██╗     ███████╗ ██████╗      ║"
    echo "║     ██║██║    ╚══██╔══╝██╔════╝██║     ██╔════╝██╔════╝      ║"
    echo "║     ██║██║       ██║   █████╗  ██║     █████╗  ██║  ███╗     ║"
    echo "║     ██║██║       ██║   ██╔══╝  ██║     ██╔══╝  ██║   ██║     ║"
    echo "║     ██║██║       ██║   ███████╗███████╗███████╗╚██████╔╝     ║"
    echo "║     ╚═╝╚═╝       ╚═╝   ╚══════╝╚══════╝╚══════╝ ╚═════╝      ║"
    echo "║                                                              ║"
    echo "║              II Telegram Agent Installer                     ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Check for required commands
check_dependencies() {
    echo -e "${CYAN}Checking dependencies...${NC}"
    
    local missing=()
    
    if ! command -v python3 &> /dev/null; then
        missing+=("python3")
    fi
    
    if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
        missing+=("pip")
    fi
    
    if ! command -v git &> /dev/null; then
        missing+=("git")
    fi
    
    if [ ${#missing[@]} -gt 0 ]; then
        echo -e "${RED}Missing dependencies: ${missing[*]}${NC}"
        echo -e "${YELLOW}Installing missing dependencies...${NC}"
        
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip python3-venv git
        elif command -v yum &> /dev/null; then
            sudo yum install -y python3 python3-pip git
        elif command -v brew &> /dev/null; then
            brew install python3 git
        else
            echo -e "${RED}Cannot auto-install dependencies. Please install: ${missing[*]}${NC}"
            exit 1
        fi
    fi
    
    echo -e "${GREEN}✓ All dependencies available${NC}"
}

# Prompt with default value
prompt_with_default() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    
    echo -ne "${CYAN}${prompt}${NC}"
    if [ -n "$default" ]; then
        echo -ne " ${YELLOW}[$default]${NC}"
    fi
    echo -ne ": "
    read -r input
    
    if [ -z "$input" ]; then
        eval "$var_name='$default'"
    else
        eval "$var_name='$input'"
    fi
}

# Prompt for required value
prompt_required() {
    local prompt="$1"
    local var_name="$2"
    local secret="${3:-false}"
    
    while true; do
        echo -ne "${CYAN}${prompt}${NC}: "
        if [ "$secret" = "true" ]; then
            read -rs input
            echo
        else
            read -r input
        fi
        
        if [ -n "$input" ]; then
            eval "$var_name='$input'"
            break
        else
            echo -e "${RED}This field is required. Please enter a value.${NC}"
        fi
    done
}

# Prompt for choice
prompt_choice() {
    local prompt="$1"
    local var_name="$2"
    shift 2
    local options=("$@")
    
    echo -e "${CYAN}${prompt}${NC}"
    local i=1
    for opt in "${options[@]}"; do
        echo -e "  ${YELLOW}$i)${NC} $opt"
        ((i++))
    done
    
    while true; do
        echo -ne "${CYAN}Enter choice [1-${#options[@]}]${NC}: "
        read -r choice
        
        if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#options[@]}" ]; then
            eval "$var_name='${options[$((choice-1))]}'" 
            break
        else
            echo -e "${RED}Invalid choice. Please enter a number between 1 and ${#options[@]}.${NC}"
        fi
    done
}

# Main installation
main() {
    print_banner
    
    echo -e "${BOLD}Welcome to the II Telegram Agent installer!${NC}"
    echo -e "This wizard will help you set up your personal AI assistant.\n"
    
    # Check dependencies
    check_dependencies
    
    # Installation directory
    INSTALL_DIR="${HOME}/.ii-telegram-agent"
    prompt_with_default "Installation directory" "$INSTALL_DIR" "INSTALL_DIR"
    
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}Step 1: Telegram Bot Setup${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    
    echo -e "To create a Telegram bot:"
    echo -e "  1. Open Telegram and search for ${YELLOW}@BotFather${NC}"
    echo -e "  2. Send ${YELLOW}/newbot${NC} and follow the instructions"
    echo -e "  3. Copy the bot token provided\n"
    
    prompt_required "Enter your Telegram Bot Token" "TELEGRAM_BOT_TOKEN" true
    
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}Step 2: AI Provider Setup${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    
    prompt_choice "Select your primary AI provider" "AI_PROVIDER" \
        "Anthropic (Claude)" \
        "OpenAI (GPT)" \
        "Google (Gemini)" \
        "OpenRouter (Multiple models)"
    
    case "$AI_PROVIDER" in
        "Anthropic (Claude)")
            echo -e "\nGet your API key from: ${YELLOW}https://console.anthropic.com/${NC}"
            prompt_required "Enter your Anthropic API Key" "ANTHROPIC_API_KEY" true
            DEFAULT_MODEL="claude-sonnet-4-20250514"
            ;;
        "OpenAI (GPT)")
            echo -e "\nGet your API key from: ${YELLOW}https://platform.openai.com/api-keys${NC}"
            prompt_required "Enter your OpenAI API Key" "OPENAI_API_KEY" true
            DEFAULT_MODEL="gpt-4o"
            ;;
        "Google (Gemini)")
            echo -e "\nGet your API key from: ${YELLOW}https://makersuite.google.com/app/apikey${NC}"
            prompt_required "Enter your Google API Key" "GEMINI_API_KEY" true
            DEFAULT_MODEL="gemini-2.0-flash"
            ;;
        "OpenRouter (Multiple models)")
            echo -e "\nGet your API key from: ${YELLOW}https://openrouter.ai/keys${NC}"
            prompt_required "Enter your OpenRouter API Key" "OPENROUTER_API_KEY" true
            DEFAULT_MODEL="anthropic/claude-sonnet-4-20250514"
            ;;
    esac
    
    prompt_with_default "Default model" "$DEFAULT_MODEL" "DEFAULT_MODEL"
    
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}Step 3: Tell Me About Yourself${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    
    echo -e "This information helps your assistant personalize responses.\n"
    
    prompt_with_default "Your name" "" "USER_NAME"
    prompt_with_default "Your timezone (e.g., America/New_York, Europe/London)" "UTC" "USER_TIMEZONE"
    prompt_with_default "What do you do? (work, hobbies, projects)" "" "USER_OCCUPATION"
    prompt_with_default "Any goals or priorities to focus on?" "" "USER_GOALS"
    
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}Step 4: Customize Your Assistant's Personality${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    
    prompt_choice "How should your assistant communicate?" "COMM_STYLE" \
        "Casual and friendly" \
        "Professional and formal" \
        "Direct and concise" \
        "Warm and supportive" \
        "Playful and witty"
    
    prompt_choice "How proactive should your assistant be?" "PROACTIVE_STYLE" \
        "Proactive - offer suggestions and anticipate needs" \
        "Balanced - help when asked, occasionally suggest" \
        "Reactive - only respond when directly asked"
    
    prompt_with_default "Give your assistant a name" "II" "ASSISTANT_NAME"
    
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}Step 5: Optional Features${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    
    echo -ne "${CYAN}Enable web search capability? [Y/n]${NC}: "
    read -r enable_search
    if [[ "${enable_search,,}" != "n" ]]; then
        echo -e "\nGet a free API key from: ${YELLOW}https://tavily.com/${NC}"
        prompt_with_default "Tavily API Key (optional, press Enter to skip)" "" "TAVILY_API_KEY"
    fi
    
    echo -ne "\n${CYAN}Enable code execution? [Y/n]${NC}: "
    read -r enable_code
    ENABLE_CODE_EXECUTION="false"
    if [[ "${enable_code,,}" != "n" ]]; then
        ENABLE_CODE_EXECUTION="true"
    fi
    
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}Installing II Telegram Agent...${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    
    # Create installation directory
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    
    # Clone or update repository
    if [ -d ".git" ]; then
        echo -e "${CYAN}Updating existing installation...${NC}"
        git pull origin main
    else
        echo -e "${CYAN}Cloning repository...${NC}"
        git clone https://github.com/Jack-Batman/ii-telegram-agent.git .
    fi
    
    # Create workspace directory
    WORKSPACE_DIR="$INSTALL_DIR/workspace"
    mkdir -p "$WORKSPACE_DIR"
    
    # Create .env file
    echo -e "${CYAN}Creating configuration...${NC}"
    cat > "$INSTALL_DIR/.env" << EOF
# II Telegram Agent Configuration
# Generated by installer on $(date)

# Telegram
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}

# AI Provider
DEFAULT_MODEL=${DEFAULT_MODEL}
EOF

    # Add API keys based on provider
    [ -n "${ANTHROPIC_API_KEY:-}" ] && echo "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}" >> "$INSTALL_DIR/.env"
    [ -n "${OPENAI_API_KEY:-}" ] && echo "OPENAI_API_KEY=${OPENAI_API_KEY}" >> "$INSTALL_DIR/.env"
    [ -n "${GEMINI_API_KEY:-}" ] && echo "GEMINI_API_KEY=${GEMINI_API_KEY}" >> "$INSTALL_DIR/.env"
    [ -n "${OPENROUTER_API_KEY:-}" ] && echo "OPENROUTER_API_KEY=${OPENROUTER_API_KEY}" >> "$INSTALL_DIR/.env"
    [ -n "${TAVILY_API_KEY:-}" ] && echo "TAVILY_API_KEY=${TAVILY_API_KEY}" >> "$INSTALL_DIR/.env"
    
    cat >> "$INSTALL_DIR/.env" << EOF

# Features
ENABLE_CODE_EXECUTION=${ENABLE_CODE_EXECUTION}
ENABLE_WEB_SEARCH=$([ -n "${TAVILY_API_KEY:-}" ] && echo "true" || echo "false")

# Paths
WORKSPACE_DIR=${WORKSPACE_DIR}
EOF

    # Create USER.md
    echo -e "${CYAN}Creating user profile...${NC}"
    cat > "$WORKSPACE_DIR/USER.md" << EOF
# User Profile

## Identity
- **Name**: ${USER_NAME:-Not specified}
- **Timezone**: ${USER_TIMEZONE:-UTC}

## About
${USER_OCCUPATION:-Not specified}

## Goals & Priorities
${USER_GOALS:-Not specified}

## Communication Preferences
- Preferred style: ${COMM_STYLE}
- Assistant proactivity: ${PROACTIVE_STYLE}

## Notes
<!-- Add any other information you want your assistant to know -->

EOF

    # Create SOUL.md based on personality choices
    echo -e "${CYAN}Creating assistant personality...${NC}"
    
    # Map communication style to personality traits
    case "$COMM_STYLE" in
        "Casual and friendly")
            PERSONALITY_TRAITS="friendly, approachable, uses casual language, occasionally uses emojis"
            TONE="warm and relaxed, like talking to a helpful friend"
            ;;
        "Professional and formal")
            PERSONALITY_TRAITS="professional, precise, uses formal language, maintains proper decorum"
            TONE="polished and respectful, like a trusted advisor"
            ;;
        "Direct and concise")
            PERSONALITY_TRAITS="efficient, straightforward, avoids unnecessary words, gets to the point"
            TONE="clear and focused, respecting the user's time"
            ;;
        "Warm and supportive")
            PERSONALITY_TRAITS="encouraging, empathetic, patient, celebrates successes"
            TONE="nurturing and understanding, like a supportive mentor"
            ;;
        "Playful and witty")
            PERSONALITY_TRAITS="clever, humorous, creative with language, enjoys wordplay"
            TONE="entertaining and engaging, bringing levity to interactions"
            ;;
    esac
    
    case "$PROACTIVE_STYLE" in
        "Proactive - offer suggestions and anticipate needs")
            PROACTIVE_BEHAVIOR="Actively suggest improvements, offer relevant information before being asked, and anticipate the user's needs based on context and past conversations."
            ;;
        "Balanced - help when asked, occasionally suggest")
            PROACTIVE_BEHAVIOR="Primarily respond to direct requests, but occasionally offer helpful suggestions when they seem particularly relevant or valuable."
            ;;
        "Reactive - only respond when directly asked")
            PROACTIVE_BEHAVIOR="Wait for explicit requests before providing information or assistance. Don't volunteer suggestions unless specifically asked."
            ;;
    esac
    
    cat > "$WORKSPACE_DIR/SOUL.md" << EOF
# ${ASSISTANT_NAME}'s Soul

## Identity
I am ${ASSISTANT_NAME}, a personal AI assistant. I exist to help, support, and assist my user in whatever way they need.

## Personality
My core traits are: ${PERSONALITY_TRAITS}

My conversational tone is ${TONE}.

## Communication Style
- I adapt my responses to match the complexity of the question
- I'm honest about my limitations and uncertainties
- I ask clarifying questions when needed rather than making assumptions
- I remember context from our conversations and reference it when relevant

## Proactivity
${PROACTIVE_BEHAVIOR}

## Values
- **Helpfulness**: I prioritize being genuinely useful
- **Honesty**: I'm truthful about what I know and don't know
- **Respect**: I treat the user's time, privacy, and preferences with care
- **Growth**: I learn from our interactions to serve better over time

## Boundaries
- I will ask before taking significant actions
- I won't pretend to have access to information I don't have
- I'll flag when a request might have unintended consequences
- I respect privacy and won't share or store sensitive information inappropriately

## Memory
I have access to our conversation history and important memories saved in MEMORY.md. I use this context to provide more personalized and relevant assistance.

EOF

    # Create MEMORY.md
    echo -e "${CYAN}Creating memory file...${NC}"
    cat > "$WORKSPACE_DIR/MEMORY.md" << EOF
# Long-Term Memory

This file stores important information that ${ASSISTANT_NAME} should remember across conversations.

## User Preferences
<!-- Automatically updated based on conversations -->

## Important Facts
<!-- Key information the user has shared -->

## Ongoing Projects
<!-- Projects the user is working on -->

## Reminders & Notes
<!-- Things to remember -->

---
*Last updated: $(date)*
EOF

    # Create AGENTS.md
    echo -e "${CYAN}Creating agent configuration...${NC}"
    cat > "$WORKSPACE_DIR/AGENTS.md" << EOF
# Agent Configuration

## Available Tools
- **Web Search**: Search the internet for current information
- **Code Execution**: Run Python code for calculations and analysis
- **Browser**: Browse websites and extract information
- **Memory**: Remember and recall information across sessions

## Capabilities
- Multi-turn conversations with context awareness
- Persistent memory across sessions
- Tool usage for enhanced functionality
- Personalized responses based on user profile

## Usage Notes
- The agent reads USER.md to understand who you are
- The agent follows SOUL.md for personality and behavior
- Important information is saved to MEMORY.md
- All tools require explicit or implicit user permission

EOF

    # Setup Python environment
    echo -e "${CYAN}Setting up Python environment...${NC}"
    python3 -m venv "$INSTALL_DIR/venv"
    source "$INSTALL_DIR/venv/bin/activate"
    pip install --upgrade pip
    pip install -e "$INSTALL_DIR"
    
    # Create start script
    cat > "$INSTALL_DIR/start.sh" << 'EOF'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/venv/bin/activate"
source "$SCRIPT_DIR/.env"
export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
python -m ii_telegram_agent.telegram.bot
EOF
    chmod +x "$INSTALL_DIR/start.sh"
    
    # Create systemd service (optional)
    cat > "$INSTALL_DIR/ii-telegram-agent.service" << EOF
[Unit]
Description=II Telegram Agent
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/start.sh
Restart=always
RestartSec=10
Environment=PATH=$INSTALL_DIR/venv/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF

    echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}${BOLD}✓ Installation Complete!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    
    echo -e "Your II Telegram Agent is ready!\n"
    
    echo -e "${BOLD}Quick Start:${NC}"
    echo -e "  ${CYAN}cd $INSTALL_DIR && ./start.sh${NC}\n"
    
    echo -e "${BOLD}Run as a Service (Linux):${NC}"
    echo -e "  ${CYAN}sudo cp $INSTALL_DIR/ii-telegram-agent.service /etc/systemd/system/${NC}"
    echo -e "  ${CYAN}sudo systemctl enable ii-telegram-agent${NC}"
    echo -e "  ${CYAN}sudo systemctl start ii-telegram-agent${NC}\n"
    
    echo -e "${BOLD}Configuration Files:${NC}"
    echo -e "  ${YELLOW}$WORKSPACE_DIR/USER.md${NC}    - Your profile (edit anytime)"
    echo -e "  ${YELLOW}$WORKSPACE_DIR/SOUL.md${NC}    - Assistant personality"
    echo -e "  ${YELLOW}$WORKSPACE_DIR/MEMORY.md${NC}  - Long-term memory\n"
    
    echo -e "${BOLD}Start chatting:${NC}"
    echo -e "  Open Telegram and message your bot!\n"
    
    echo -ne "${CYAN}Would you like to start the bot now? [Y/n]${NC}: "
    read -r start_now
    if [[ "${start_now,,}" != "n" ]]; then
        echo -e "\n${GREEN}Starting II Telegram Agent...${NC}"
        exec "$INSTALL_DIR/start.sh"
    fi
}

main "$@"