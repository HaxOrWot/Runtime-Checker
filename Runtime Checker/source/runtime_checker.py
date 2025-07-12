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
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dest_file_path = os.path.join(script_dir, DEST_FILE)
    code_folder_path = None

    default_code_folder_path = os.path.join(script_dir, CODE_FOLDER_NAME)

    stored_path_from_file = None
    if os.path.exists(dest_file_path):
        try:
            with open(dest_file_path, 'r') as f:
                stored_path_from_file = f.read().strip()
            if stored_path_from_file:
                if (os.path.isdir(stored_path_from_file) or not os.path.exists(stored_path_from_file)) and \
                   os.path.basename(stored_path_from_file).lower() == CODE_FOLDER_NAME:
                    code_folder_path = stored_path_from_file
                    print(f"Using custom code folder from '{DEST_FILE}': '{code_folder_path}'")
                else:
                    print(f"Stored path '{stored_path_from_file}' in '{DEST_FILE}' is invalid or not named '{CODE_FOLDER_NAME}'.")
            else:
                print(f"'{DEST_FILE}' is empty.")
        except Exception as e:
            print(f"Warning: Could not read '{DEST_FILE}': {e}. Will prompt for a new path.")
    else:
        print(f"'{DEST_FILE}' not found. Defaulting to '{default_code_folder_path}'.")
        code_folder_path = default_code_folder_path

    while code_folder_path is None:
        user_input = input(f"Please enter the full path to your '{CODE_FOLDER_NAME}' folder: ").strip()
        if not user_input:
            print("Path cannot be empty. Please try again.")
            continue

        user_input = os.path.abspath(user_input)

        if (os.path.isdir(user_input) or not os.path.exists(user_input)) and \
           os.path.basename(user_input).lower() == CODE_FOLDER_NAME:
            code_folder_path = user_input
        else:
            print(f"Error: '{user_input}' is not a valid directory path or not named '{CODE_FOLDER_NAME}'. Please try again.")

    try:
        os.makedirs(code_folder_path, exist_ok=True)
        print(f"Ensuring '{CODE_FOLDER_NAME}' folder exists at: '{code_folder_path}'")
    except Exception as e:
        print(f"Error: Could not create '{CODE_FOLDER_NAME}' folder at '{code_folder_path}': {e}")
        return None

    try:
        with open(dest_file_path, 'w') as f:
            f.write(code_folder_path)
        print(f"Updated '{DEST_FILE}' with the current folder path.")
    except Exception as e:
        print(f"Warning: Could not save path to '{DEST_FILE}': {e}")

    return code_folder_path

def get_file_to_run(code_folder_path):
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

    print(f"\nFound the following files in '{code_folder_path}':")
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
    results = {
        "status": "Pending",
        "runtime": 0.0,
        "output": "",
        "error": "",
        "language": "Unknown"
    }

    if not os.path.exists(file_path):
        results["status"] = "File Error"
        results["error"] = f"Error: File not found at '{file_path}'."
        return results

    file_directory = os.path.dirname(os.path.abspath(file_path))
    temp_files_dir = os.path.join(file_directory, "temp_files")

    os.makedirs(temp_files_dir, exist_ok=True)

    file_extension = os.path.splitext(file_path)[1].lower()
    language = SUPPORTED_EXTENSIONS.get(file_extension)

    if language is None:
        results["status"] = "Language Error"
        results["error"] = f"Error: Unsupported file extension '{file_extension}'. Supported: .py, .c, .cpp, .cxx, .cc, .java"
        if os.path.exists(temp_files_dir) and not os.listdir(temp_files_dir):
            os.rmdir(temp_files_dir)
        return results

    results["language"] = language

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code_content = f.read()
    except Exception as e:
        results["status"] = "File Error"
        results["error"] = f"Error reading file: {e}"
        if os.path.exists(temp_files_dir) and not os.listdir(temp_files_dir):
            os.rmdir(temp_files_dir)
        return results

    if not code_content.strip():
        results["status"] = "File Error"
        results["error"] = "Error: The provided file is empty or contains only whitespace."
        if os.path.exists(temp_files_dir) and not os.listdir(temp_files_dir):
            os.rmdir(temp_files_dir)
        return results

    command = []
    temp_exec_path = None
    process = None

    try:
        if language == "python":
            command = ["python3", file_path]
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
            class_name = os.path.splitext(os.path.basename(file_path))[0]
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
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                return results
            command = ["java", "-cp", temp_dir, class_name]
            temp_exec_path = temp_dir


        start_time = time.perf_counter()
        try:
            process = subprocess.run(
                command,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=time_limit,
                check=False
            )
            end_time = time.perf_counter()
            results["runtime"] = (end_time - start_time) * 1000
            results["output"] = process.stdout.strip()
            results["error"] = process.stderr.strip()

            if process.returncode != 0:
                results["status"] = "Runtime Error"
                if not results["error"]:
                    results["error"] = f"Process exited with non-zero status code: {process.returncode}"
            else:
                results["status"] = "Success"

        except subprocess.TimeoutExpired:
            if process and process.poll() is None:
                process.kill()
            end_time = time.perf_counter()
            results["runtime"] = (end_time - start_time) * 1000
            results["status"] = "Time Limit Exceeded"
            results["error"] = f"Execution exceeded time limit of {time_limit} seconds."
        except FileNotFoundError:
            results["status"] = "Runtime Error"
            results["error"] = f"Error: Interpreter/compiler not found for {language}. Make sure it's in your PATH."
        except Exception as e:
            results["status"] = "Internal Error"
            results["error"] = f"An unexpected error occurred during execution: {e}"

    finally:
        if language in ["c", "cpp"] and temp_exec_path and os.path.exists(temp_exec_path):
            os.remove(temp_exec_path)
        if language == "java" and temp_exec_path and os.path.exists(temp_exec_path):
            shutil.rmtree(temp_exec_path, ignore_errors=True)

        if os.path.exists(temp_files_dir) and not os.listdir(temp_files_dir):
            os.rmdir(temp_files_dir)

    return results

# --- Main execution logic ---
if __name__ == "__main__":
    code_folder = get_code_folder_path()

    if code_folder:
        while True:
            selected_file_full_path = get_file_to_run(code_folder)

            if selected_file_full_path:
                file_extension = os.path.splitext(selected_file_full_path)[1].lower()
                input_data = None
                if file_extension in SUPPORTED_EXTENSIONS:
                    user_wants_input = input("Does this code require input? (yes/no): ").strip().lower()
                    if user_wants_input == 'yes':
                        print("Enter input data. Type 'DONE' on a new line when finished:")
                        input_lines = []
                        while True:
                            line = input()
                            if line.strip().lower() == 'done':
                                break
                            input_lines.append(line)
                        input_data = "\n".join(input_lines)
                        if not input_data.strip():
                            input_data = None

                print(f"\n--- Running '{os.path.basename(selected_file_full_path)}' ---")
                results = run_code_from_file(selected_file_full_path, input_data=input_data)
                print(f"Status: {results['status']}")
                print(f"Language: {results['language']}")
                print(f"Runtime: {results['runtime']:.2f} MS")
                print(f"Output:\n{results['output']}")
                if results['error']:
                    print(f"Error:\n{results['error']}")
                print("\n" + "="*50 + "\n")
            else:
                print("No file selected or folder is empty. Cannot proceed with execution.")
                pass

            while True:
                quit_choice = input("Do you want to quit? (yes/no): ").strip().lower()
                if quit_choice == 'yes':
                    print("Exiting..... Exited")
                    exit()
                elif quit_choice == 'no':
                    print("\n--- Preparing for next code check ---")
                    break
                else:
                    print("Invalid choice. Please enter 'yes' or 'no'.")
    else:
        print("Could not determine a valid code folder. Exiting.")
