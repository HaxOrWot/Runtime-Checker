import subprocess
import time
import os
import tempfile
import shutil

# --- Configuration ---
DEST_FILE = "dest.txt"
CODE_FOLDER_NAME = "check_code"
SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".c": "c",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".cc": "cpp",
    ".java": "java"
}

def get_code_folder_path():
    """
    Manages the persistent storage and retrieval of the 'check_code' folder path.
    - If dest.txt is missing, it defaults to creating 'check_code' in the script's directory.
    - If dest.txt exists and contains a valid path, it uses that.
    - If dest.txt exists but is empty or contains an invalid path, it prompts the user.
    - Automatically creates the 'check_code' folder at the determined path if it doesn't exist.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dest_file_path = os.path.join(script_dir, DEST_FILE)
    code_folder_path = None # This will hold the final, valid path

    # Determine the default path if no custom path is provided/valid
    default_code_folder_path = os.path.join(script_dir, CODE_FOLDER_NAME)

    # 1. Try to read the path from dest.txt
    stored_path_from_file = None
    if os.path.exists(dest_file_path):
        try:
            with open(dest_file_path, 'r') as f:
                stored_path_from_file = f.read().strip()
            if stored_path_from_file:
                # Validate the stored path: Is it a directory OR does it not exist (for creation)?
                # And does it have the correct folder name?
                if (os.path.isdir(stored_path_from_file) or not os.path.exists(stored_path_from_file)) and \
                   os.path.basename(stored_path_from_file).lower() == CODE_FOLDER_NAME:
                    code_folder_path = stored_path_from_file
                    print(f"Using custom code folder from '{DEST_FILE}': '{code_folder_path}'")
                else:
                    print(f"Stored path '{stored_path_from_file}' in '{DEST_FILE}' is invalid or not named '{CODE_FOLDER_NAME}'.")
            else:
                print(f"'{DEST_FILE}' is empty. Will prompt for a new path.")
        except Exception as e:
            print(f"Warning: Could not read '{DEST_FILE}': {e}. Will prompt for a new path.")
    else:
        print(f"'{DEST_FILE}' not found. Defaulting to '{default_code_folder_path}'.")
        code_folder_path = default_code_folder_path # Condition 1: Default if dest.txt doesn't exist

    # 2. If code_folder_path is still None (meaning dest.txt was empty or invalid), prompt the user
    while code_folder_path is None:
        user_input = input(f"Please enter the full path to your '{CODE_FOLDER_NAME}' folder: ").strip()
        if not user_input:
            print("Path cannot be empty. Please try again.")
            continue

        # Normalize path to handle different OS conventions
        user_input = os.path.abspath(user_input)

        # Validate user input: Allow if it's an existing directory OR if it doesn't exist but has the correct name
        if (os.path.isdir(user_input) or not os.path.exists(user_input)) and \
           os.path.basename(user_input).lower() == CODE_FOLDER_NAME:
            code_folder_path = user_input # Accept this as a potential path
        else:
            print(f"Error: '{user_input}' is not a valid directory path or not named '{CODE_FOLDER_NAME}'. Please try again.")

    # 3. Once code_folder_path is determined (from default, file, or user input), ensure the directory exists
    try:
        os.makedirs(code_folder_path, exist_ok=True)
        print(f"Ensured '{CODE_FOLDER_NAME}' folder exists at: '{code_folder_path}'")
    except Exception as e:
        print(f"Error: Could not create '{CODE_FOLDER_NAME}' folder at '{code_folder_path}': {e}")
        return None # Critical error, cannot proceed

    # 4. Save the final determined path to dest.txt
    # This ensures dest.txt always holds the currently used and valid path
    try:
        with open(dest_file_path, 'w') as f:
            f.write(code_folder_path)
        print(f"Updated '{DEST_FILE}' with the current code folder path.")
    except Exception as e:
        print(f"Warning: Could not save path to '{DEST_FILE}': {e}")

    return code_folder_path

def get_file_to_run(code_folder_path):
    """
    Lists supported code files in the given folder and prompts the user to select one.
    """
    supported_files = []
    for filename in os.listdir(code_folder_path):
        file_path = os.path.join(code_folder_path, filename)
        if os.path.isfile(file_path):
            file_extension = os.path.splitext(filename)[1].lower()
            if file_extension in SUPPORTED_EXTENSIONS:
                supported_files.append(filename)

    if not supported_files:
        print(f"Error: No supported code files found in '{code_folder_path}'.")
        print("Please place .py, .c, .cpp, or .java files inside this folder.")
        return None

    print(f"\nFound the following code files in '{code_folder_path}':")
    for i, filename in enumerate(supported_files):
        print(f"  {i + 1}. {filename}")

    selected_file_name = None
    while selected_file_name is None:
        user_input = input("Enter the name of the file you want to check (e.g., my_code.py): ").strip()
        if not user_input:
            print("File name cannot be empty. Please try again.")
            continue

        if user_input in supported_files:
            selected_file_name = user_input
        else:
            print(f"Error: '{user_input}' not found or not a supported code file in the list. Please try again.")

    return os.path.join(code_folder_path, selected_file_name)


def run_code_from_file(file_path, time_limit=10, input_data=None):
    """
    Reads code from a file, determines its language, executes it,
    and measures its runtime. Temporary files are stored in a 'temp_files'
    subfolder created alongside the input file.

    Args:
        file_path (str): The path to the code file.
        time_limit (int): Maximum execution time allowed in seconds.
        input_data (str, optional): String data to be passed as standard input to the program.
                                     Defaults to None (no input).

    Returns:
        dict: A dictionary containing the execution results:
              - 'status': "Success", "File Error", "Language Error",
                          "Compilation Error", "Runtime Error", "Time Limit Exceeded"
              - 'runtime': Float, execution time in milliseconds
              - 'output': String, standard output of the program
              - 'error': String, standard error or error message
              - 'language': String, detected language
    """
    results = {
        "status": "Pending",
        "runtime": 0.0,
        "output": "",
        "error": "",
        "language": "Unknown"
    }

    # 1. Check if file exists (already checked by get_file_to_run, but good for robustness)
    if not os.path.exists(file_path):
        results["status"] = "File Error"
        results["error"] = f"Error: File not found at '{file_path}'."
        return results

    # Determine the directory of the input file (which is inside check_code)
    file_directory = os.path.dirname(os.path.abspath(file_path))
    temp_files_dir = os.path.join(file_directory, "temp_files")

    # Create the temp_files directory if it doesn't exist
    os.makedirs(temp_files_dir, exist_ok=True)

    # 2. Determine language from extension
    file_extension = os.path.splitext(file_path)[1].lower()
    language = SUPPORTED_EXTENSIONS.get(file_extension)

    if language is None: # Should not happen if get_file_to_run works correctly
        results["status"] = "Language Error"
        results["error"] = f"Error: Unsupported file extension '{file_extension}'. Supported: .py, .c, .cpp, .cxx, .cc, .java"
        # Clean up temp_files directory if it was created and is empty
        if os.path.exists(temp_files_dir) and not os.listdir(temp_files_dir):
            os.rmdir(temp_files_dir)
        return results

    results["language"] = language

    # 3. Read code from file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code_content = f.read()
    except Exception as e:
        results["status"] = "File Error"
        results["error"] = f"Error reading file: {e}"
        # Clean up temp_files directory if it was created and is empty
        if os.path.exists(temp_files_dir) and not os.listdir(temp_files_dir):
            os.rmdir(temp_files_dir)
        return results

    # 4. Check for empty file
    if not code_content.strip(): # .strip() removes whitespace
        results["status"] = "File Error"
        results["error"] = "Error: The provided file is empty or contains only whitespace."
        # Clean up temp_files directory if it was created and is empty
        if os.path.exists(temp_files_dir) and not os.listdir(temp_files_dir):
            os.rmdir(temp_files_dir)
        return results

    # Prepare for execution
    command = []
    temp_exec_path = None # To store path of compiled executable/class file/temp dir
    process = None # Initialize process to None to prevent UnboundLocalError

    try:
        if language == "python":
            # Directly use the system's python3 or python command
            # This assumes python3/python is in the system's PATH
            command = ["python3", file_path]
            # Fallback to 'python' if 'python3' is not found (common on some systems)
            try:
                subprocess.run(["python3", "--version"], check=True, capture_output=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                command = ["python", file_path]
                try:
                    subprocess.run(["python", "--version"], check=True, capture_output=True)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    results["status"] = "Runtime Error"
                    results["error"] = "Error: Neither 'python3' nor 'python' command found. Please ensure Python is installed and in your system's PATH."
                    return results

        elif language == "c":
            # Create a temporary output file for the executable inside temp_files_dir
            with tempfile.NamedTemporaryFile(delete=False, suffix=".out", dir=temp_files_dir) as tmp_exec:
                temp_exec_path = tmp_exec.name

            compile_command = ["gcc", file_path, "-o", temp_exec_path]
            compile_process = subprocess.run(
                compile_command,
                capture_output=True,
                text=True,
                timeout=time_limit
            )
            if compile_process.returncode != 0:
                results["status"] = "Compilation Error"
                results["error"] = compile_process.stderr
                return results
            command = [temp_exec_path]
        elif language == "cpp":
            # Create a temporary output file for the executable inside temp_files_dir
            with tempfile.NamedTemporaryFile(delete=False, suffix=".out", dir=temp_files_dir) as tmp_exec:
                temp_exec_path = tmp_exec.name

            compile_command = ["g++", file_path, "-o", temp_exec_path]
            compile_process = subprocess.run(
                compile_command,
                capture_output=True,
                text=True,
                timeout=time_limit
            )
            if compile_process.returncode != 0:
                results["status"] = "Compilation Error"
                results["error"] = compile_process.stderr
                return results
            command = [temp_exec_path]
        elif language == "java":
            # Java requires the class name to match the file name (without .java)
            class_name = os.path.splitext(os.path.basename(file_path))[0]
            # Create a temporary directory for Java class files inside temp_files_dir
            temp_dir = tempfile.mkdtemp(dir=temp_files_dir)
            compile_command = ["javac", "-d", temp_dir, file_path]
            compile_process = subprocess.run(
                compile_command,
                capture_output=True,
                text=True,
                timeout=time_limit
            )
            if compile_process.returncode != 0:
                results["status"] = "Compilation Error"
                results["error"] = compile_process.stderr
                # Clean up temp dir even on compilation error
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                return results
            command = ["java", "-cp", temp_dir, class_name]
            temp_exec_path = temp_dir # Store temp dir for cleanup


        # 5. Run the code and measure time
        start_time = time.perf_counter()
        try:
            process = subprocess.run( # 'process' is assigned here
                command,
                input=input_data, # Pass input_data to the stdin of the subprocess
                capture_output=True,
                text=True,
                timeout=time_limit,
                check=False # Do not raise CalledProcessError for non-zero exit codes
            )
            end_time = time.perf_counter()
            # Convert runtime from seconds to milliseconds
            results["runtime"] = (end_time - start_time) * 1000
            results["output"] = process.stdout.strip()
            results["error"] = process.stderr.strip()

            if process.returncode != 0:
                results["status"] = "Runtime Error"
                if not results["error"]: # If stderr is empty, but return code is non-zero
                    results["error"] = f"Process exited with non-zero status code: {process.returncode}"
            else:
                results["status"] = "Success"

        except subprocess.TimeoutExpired:
            # If a timeout occurs, process will be defined by subprocess.run
            # but it might still be running. We explicitly kill it.
            if process and process.poll() is None: # Check if process is still running
                process.kill() # Ensure the process is terminated
            end_time = time.perf_counter()
            # Convert runtime from seconds to milliseconds
            results["runtime"] = (end_time - start_time) * 1000 # Record time up to timeout
            results["status"] = "Time Limit Exceeded"
            results["error"] = f"Execution exceeded time limit of {time_limit} seconds."
        except FileNotFoundError:
            results["status"] = "Runtime Error"
            results["error"] = f"Error: Interpreter/compiler not found for {language}. Make sure it's in your PATH."
        except Exception as e:
            results["status"] = "Internal Error"
            results["error"] = f"An unexpected error occurred during execution: {e}"

    finally:
        # Clean up temporary files/directories
        if language in ["c", "cpp"] and temp_exec_path and os.path.exists(temp_exec_path):
            os.remove(temp_exec_path)
        if language == "java" and temp_exec_path and os.path.exists(temp_exec_path):
            shutil.rmtree(temp_exec_path, ignore_errors=True)

        # Clean up the temp_files directory if it's empty after all operations
        if os.path.exists(temp_files_dir) and not os.listdir(temp_files_dir):
            os.rmdir(temp_files_dir)


    return results

# --- Main execution logic ---
if __name__ == "__main__":
    # Get the code folder path (handles persistence and automatic creation)
    code_folder = get_code_folder_path()

    if code_folder:
        while True: # Loop indefinitely until user decides to quit
            # Get the specific file to run from the code folder
            selected_file_full_path = get_file_to_run(code_folder)

            if selected_file_full_path:
                # Ask for input data if the file is a Python, C, C++, or Java file
                file_extension = os.path.splitext(selected_file_full_path)[1].lower()
                input_data = None # Initialize input_data to None
                if file_extension in SUPPORTED_EXTENSIONS:
                    user_wants_input = input("Does this code require input? (yes/no): ").strip().lower()
                    if user_wants_input == 'yes':
                        input_data = input("Enter input data (use '\\n' for new lines): ")
                    # If user_wants_input is 'no' or anything else, input_data remains None

                print(f"\n--- Running '{os.path.basename(selected_file_full_path)}' ---")
                results = run_code_from_file(selected_file_full_path, input_data=input_data)
                print(f"Status: {results['status']}")
                print(f"Language: {results['language']}")
                # Display runtime in milliseconds
                print(f"Runtime: {results['runtime']:.2f} MS")
                print(f"Output:\n{results['output']}")
                if results['error']:
                    print(f"Error:\n{results['error']}")
                print("\n" + "="*50 + "\n")
            else:
                print("No file selected or folder is empty. Cannot proceed with execution.")
                # If no file is selected, ask if they want to try again or quit
                # This prevents an infinite loop if the folder is empty and they keep saying 'no'
                # to selecting a file.
                pass # Let the quit prompt handle this

            # Ask user if they want to quit or run another file
            while True:
                quit_choice = input("Do you want to quit? (yes/no): ").strip().lower()
                if quit_choice == 'yes':
                    print("Exiting..... Exited")
                    exit() # Use exit() to terminate the script
                elif quit_choice == 'no':
                    print("\n--- Preparing for next code check ---")
                    break # Break out of the inner loop to continue the outer while True loop
                else:
                    print("Invalid choice. Please enter 'yes' or 'no'.")
    else:
        print("Could not determine a valid code folder. Exiting.")
