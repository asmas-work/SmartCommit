import streamlit as st
import os
from dotenv import load_dotenv
from git import Repo, InvalidGitRepositoryError, GitCommandError
import gpt_utils
import difflib
import tempfile
import shutil
import subprocess
from urllib.parse import urlparse
import time
import stat
import errno

# Load environment variables
load_dotenv()

# Get the generic API key from environment variables
GENERIC_API_KEY = os.getenv("OPENAI_API_KEY")

def init_session_state():
    """Initialize session state variables"""
    if 'api_key' not in st.session_state:
        st.session_state.api_key = GENERIC_API_KEY
    if 'key_type' not in st.session_state:
        st.session_state.key_type = "generic" if GENERIC_API_KEY else "personal"
    if 'temp_dir' not in st.session_state:
        st.session_state.temp_dir = None

# Initialize session state at startup
init_session_state()

def run_git_command(cmd, cwd=None):
    """Run a git command and return its output"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=True,
            env=os.environ.copy()  # Use current environment variables
        )
        if result.returncode == 0:
            return result.stdout.strip()
        st.error(f"Git command failed: {result.stderr.strip()}")
        return None
    except Exception as e:
        st.error(f"Git command error: {str(e)}")
        return None

def get_repo_name_from_url(url):
    """Extract repository name from GitHub URL"""
    try:
        path = urlparse(url).path
        return path.strip('/').split('/')[-1].replace('.git', '')
    except:
        return 'remote_repo'

def force_remove_directory(path):
    """Force remove a directory and its contents on Windows"""
    def handle_remove_readonly(func, path, exc):
        excvalue = exc[1]
        if func in (os.rmdir, os.remove, os.unlink) and excvalue.errno == errno.EACCES:
            # Change the file to be readable, writable, and executable
            os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
            try:
                func(path)
            except Exception:
                # If changing permissions didn't work, try to force delete
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    shutil.rmtree(path, ignore_errors=True)

    max_retries = 5
    for attempt in range(max_retries):
        try:
            if os.path.exists(path):
                # First try to kill any processes that might be using the directory
                if os.name == 'nt':  # Windows
                    try:
                        os.system(f'taskkill /F /IM "git.exe" 2>nul')
                        time.sleep(0.5)  # Wait for processes to be killed
                    except Exception:
                        pass

                # Try to remove the directory
                shutil.rmtree(path, onerror=handle_remove_readonly)
                
                # Double check it's gone
                if os.path.exists(path):
                    time.sleep(0.5)  # Wait a bit before retry
                    continue
                
                return True  # Successfully removed
            return True  # Path doesn't exist, consider it removed
        except Exception as e:
            if attempt == max_retries - 1:  # Last attempt
                st.error(f"Failed to remove directory after {max_retries} attempts: {str(e)}")
                return False
            time.sleep(0.5)  # Wait before retrying
    return False

def cleanup():
    """Clean up temporary directories with improved Windows support"""
    try:
        if hasattr(st.session_state, 'temp_dir') and st.session_state.temp_dir:
            temp_dir = st.session_state.temp_dir
            st.session_state.temp_dir = None  # Clear it first
            
            if os.path.exists(temp_dir):
                if not force_remove_directory(temp_dir):
                    st.warning("Could not completely clean up temporary directory. You may need to remove it manually.")
    except Exception as e:
        st.warning(f"Warning during cleanup: {str(e)}")

def get_file_diff(file1_content, file2_content):
    """Generate diff between two files"""
    diff = difflib.unified_diff(
        file1_content.splitlines(keepends=True),
        file2_content.splitlines(keepends=True),
        fromfile='file1',
        tofile='file2'
    )
    return ''.join(diff)

def setup_repository(local_path, remote_url=None):
    """Setup and validate repository for comparison"""
    try:
        # Initialize session state if not already done
        if 'temp_dir' not in st.session_state:
            st.session_state.temp_dir = None

        # Check if local path exists
        if not os.path.exists(local_path):
            return None, None, f"Local path '{local_path}' does not exist."

        # Try to initialize or open git repository
        try:
            local_repo = Repo(local_path)
        except InvalidGitRepositoryError:
            try:
                local_repo = Repo.init(local_path)
                local_repo.git.add('.')
                local_repo.git.commit('-m', 'Initial commit')
            except Exception as e:
                return None, None, f"Failed to initialize git repository: {str(e)}"

        # Handle remote repository if provided
        if remote_url:
            try:
                # Clean up any existing temporary directory
                cleanup()
                
                # Wait for cleanup to complete
                time.sleep(1)
                
                # Create new temporary directory with unique name
                base_temp = tempfile.gettempdir()
                unique_dir = f"smartcommit_{int(time.time())}"
                temp_base = os.path.join(base_temp, unique_dir)
                
                # Ensure the new directory path is clean
                if os.path.exists(temp_base):
                    if not force_remove_directory(temp_base):
                        return local_repo, None, "Failed to clean up existing temporary directory"
                
                os.makedirs(temp_base, exist_ok=True)
                st.session_state.temp_dir = temp_base
                
                repo_name = get_repo_name_from_url(remote_url)
                clone_path = os.path.join(temp_base, repo_name)
                
                # Double check clone path is clean
                if os.path.exists(clone_path):
                    if not force_remove_directory(clone_path):
                        cleanup()
                        return local_repo, None, "Failed to prepare clone directory"
                
                # Try to clone with HTTPS first
                success = False
                error_msg = ""
                
                try:
                    clone_cmd = f"git clone {remote_url} {clone_path}"
                    result = run_git_command(clone_cmd)
                    if result is not None:  # Check for None specifically
                        success = True
                    else:
                        error_msg = "HTTPS clone failed"
                except Exception as e:
                    error_msg = f"HTTPS error: {str(e)}"
                
                # Try SSH if HTTPS failed
                if not success and remote_url.startswith('https://'):
                    try:
                        ssh_url = remote_url.replace('https://', 'git@').replace('/', ':', 1)
                        clone_cmd = f"git clone {ssh_url} {clone_path}"
                        result = run_git_command(clone_cmd)
                        if result is not None:  # Check for None specifically
                            success = True
                        else:
                            error_msg += ", SSH clone failed"
                    except Exception as e:
                        error_msg += f", SSH error: {str(e)}"
                
                if not success:
                    cleanup()
                    return local_repo, None, f"Failed to clone repository: {error_msg}"
                
                if os.path.exists(clone_path):
                    try:
                        remote_repo = Repo(clone_path)
                        return local_repo, remote_repo, None
                    except Exception as e:
                        cleanup()
                        return local_repo, None, f"Error initializing cloned repository: {str(e)}"
                else:
                    cleanup()
                    return local_repo, None, "Failed to clone remote repository - directory not created"
                    
            except Exception as e:
                cleanup()
                return local_repo, None, f"Error cloning remote repository: {str(e)}"
        
        return local_repo, None, None

    except Exception as e:
        cleanup()
        return None, None, f"Error setting up repository: {str(e)}"

def get_repository_diff(local_repo, remote_repo=None):
    """Get differences between repositories"""
    try:
        changes = {
            'unstaged': '',
            'staged': '',
            'remote': ''
        }

        # Get local changes
        if local_repo.is_dirty(untracked_files=True):
            changes['unstaged'] = local_repo.git.diff()
            changes['staged'] = local_repo.git.diff('--cached')

        # Compare with remote if available
        if remote_repo:
            try:
                # Get the remote repository's default branch
                remote_branch = remote_repo.active_branch.name
                remote_commit = remote_repo.head.commit.hexsha

                # Add remote as a new remote to local repository
                remote_name = "comparison_remote"
                try:
                    local_repo.delete_remote(remote_name)
                except:
                    pass
                
                local_repo.create_remote(remote_name, remote_repo.working_dir)
                local_repo.remotes[remote_name].fetch()

                # Instead of using git diff with merge base, just get the file lists and contents
                local_files = set()
                remote_files = set()
                
                # Get list of files in local repo
                for root, _, files in os.walk(local_repo.working_dir):
                    for file in files:
                        if not file.startswith('.git'):
                            rel_path = os.path.relpath(os.path.join(root, file), local_repo.working_dir)
                            local_files.add(rel_path)

                # Get list of files in remote repo
                for root, _, files in os.walk(remote_repo.working_dir):
                    for file in files:
                        if not file.startswith('.git'):
                            rel_path = os.path.relpath(os.path.join(root, file), remote_repo.working_dir)
                            remote_files.add(rel_path)

                # Compare files
                diff_output = []
                
                # Files in both repos
                common_files = local_files.intersection(remote_files)
                for file in common_files:
                    try:
                        local_content = open(os.path.join(local_repo.working_dir, file), 'r', encoding='utf-8').read()
                        remote_content = open(os.path.join(remote_repo.working_dir, file), 'r', encoding='utf-8').read()
                        
                        if local_content != remote_content:
                            diff = difflib.unified_diff(
                                remote_content.splitlines(keepends=True),
                                local_content.splitlines(keepends=True),
                                fromfile=f'remote/{file}',
                                tofile=f'local/{file}'
                            )
                            diff_output.extend(diff)
                    except Exception as e:
                        st.warning(f"Error comparing file {file}: {str(e)}")

                # Files only in local
                only_local = local_files - remote_files
                for file in only_local:
                    diff_output.append(f"Only in local: {file}\n")

                # Files only in remote
                only_remote = remote_files - local_files
                for file in only_remote:
                    diff_output.append(f"Only in remote: {file}\n")

                changes['remote'] = ''.join(diff_output) if diff_output else "No differences found"

                # Clean up the temporary remote
                local_repo.delete_remote(remote_name)

            except Exception as e:
                st.warning(f"Warning while comparing with remote: {str(e)}")

        return changes

    except Exception as e:
        raise Exception(f"Error getting repository differences: {str(e)}")

# Main UI
st.title("SmartCommit - AI-Powered Commit Message Generator")

# Sidebar configuration
with st.sidebar:
    st.header("Configuration")
    
    # API Key Selection
    st.subheader("API Key Settings")
    key_type = st.radio(
        "Choose API Key Type",
        ["Use Generic Key", "Use Personal Key"],
        index=0 if GENERIC_API_KEY else 1
    )
    
    if key_type == "Use Personal Key":
        personal_key = st.text_input(
            "Enter Your OpenAI API Key",
            type="password",
            help="Enter your personal OpenAI API key here"
        )
        if personal_key:
            st.session_state.api_key = personal_key
            gpt_utils.gpt_client.initialize(personal_key)
            st.success("Personal API key set successfully!")
        else:
            st.warning("Please enter your OpenAI API key")
    else:
        if GENERIC_API_KEY:
            st.session_state.api_key = GENERIC_API_KEY
            gpt_utils.gpt_client.initialize(GENERIC_API_KEY)
            st.success("Using generic API key")
        else:
            st.error("No generic API key configured. Please use a personal key.")
            st.stop()
    
    # Comparison Type Selection
    st.subheader("Comparison Settings")
    comparison_type = st.radio(
        "Select Comparison Type",
        ["Git Repository", "File Comparison"]
    )

try:
    if not st.session_state.api_key:
        st.error("Please configure an API key first")
        st.stop()

    if comparison_type == "Git Repository":
        st.subheader("Git Repository Comparison")
        col1, col2 = st.columns(2)
        
        with col1:
            local_repo_path = st.text_input(
                "Local Repository Path", 
                help="Enter the full path to your local code directory"
            )
        with col2:
            remote_url = st.text_input(
                "Remote Repository URL (optional)", 
                help="Enter the GitHub repository URL to compare with (e.g., https://github.com/username/repo)"
            )
            
        if local_repo_path:
            # Setup repositories
            local_repo, remote_repo, error_msg = setup_repository(local_repo_path, remote_url)
            
            if error_msg:
                st.error(error_msg)
                if not local_repo:  # If local repo setup failed
                    st.stop()
            
            try:
                # Get all changes
                changes = get_repository_diff(local_repo, remote_repo)
                
                # Display local changes
                if changes['unstaged'] or changes['staged']:
                    st.markdown("### Local Changes")
                    
                    if changes['unstaged']:
                        st.markdown("#### Unstaged Changes")
                        st.code(changes['unstaged'], language="diff")
                    
                    if changes['staged']:
                        st.markdown("#### Staged Changes")
                        st.code(changes['staged'], language="diff")
                
                # Display remote comparison
                if changes['remote']:
                    st.markdown("### Changes Compared to Remote")
                    st.code(changes['remote'], language="diff")
                    
                    if st.button("Generate Commit Message for All Changes"):
                        with st.spinner("Generating commit message..."):
                            commit_message = gpt_utils.generate_commit_message(changes['remote'])
                            st.subheader("Suggested Commit Message")
                            st.write(commit_message)
                            
                            if st.button("Commit Changes"):
                                try:
                                    local_repo.git.add(".")
                                    local_repo.git.commit(m=commit_message)
                                    st.success("Changes committed successfully!")
                                except Exception as e:
                                    st.error(f"Error committing changes: {str(e)}")
                
                elif changes['unstaged'] or changes['staged']:
                    # Generate commit message for local changes only
                    all_changes = "\n".join(filter(None, [changes['unstaged'], changes['staged']]))
                    
                    if st.button("Generate Commit Message for Local Changes"):
                        with st.spinner("Generating commit message..."):
                            commit_message = gpt_utils.generate_commit_message(all_changes)
                            st.subheader("Suggested Commit Message")
                            st.write(commit_message)
                            
                            if st.button("Commit Changes"):
                                try:
                                    local_repo.git.add(".")
                                    local_repo.git.commit(m=commit_message)
                                    st.success("Changes committed successfully!")
                                except Exception as e:
                                    st.error(f"Error committing changes: {str(e)}")
                else:
                    if remote_repo:
                        st.info("No differences found between local and remote repositories.")
                    else:
                        st.info("No changes detected in the local repository.")
            
            except Exception as e:
                st.error(f"Error comparing repositories: {str(e)}")
    
    else:  # File Comparison
        st.subheader("File Comparison")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Original File")
            file1_content = st.text_area("Enter or paste original code", height=300)
            
        with col2:
            st.markdown("### Modified File")
            file2_content = st.text_area("Enter or paste modified code", height=300)
        
        if file1_content and file2_content:
            diff = get_file_diff(file1_content, file2_content)
            
            if diff:
                st.markdown("### Differences Detected")
                st.code(diff, language="diff")
                
                if st.button("Generate Commit Message"):
                    with st.spinner("Generating commit message..."):
                        commit_message = gpt_utils.generate_commit_message(diff)
                        st.subheader("Suggested Commit Message")
                        st.write(commit_message)
            else:
                st.info("No differences found between the files.")

finally:
    # Clean up temporary directories
    cleanup() 