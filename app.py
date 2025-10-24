import streamlit as st
import mysql.connector as cs
import pandas as pd

# Set page configuration
st.set_page_config(
    page_title="Test Management System",
    page_icon="📝",
    layout="wide"
)


# Database connection function
@st.cache_resource
def get_connection():
    try:
        conn = cs.connect(host='localhost', user='root', password='charan', database='quiz')
        if conn.is_connected():
            return conn
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return None


# Initialize session state variables if they don't exist
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'user_type' not in st.session_state:
    st.session_state.user_type = ""
if 'current_page' not in st.session_state:
    st.session_state.current_page = "home"
if 'selected_test' not in st.session_state:
    st.session_state.selected_test = None
if 'current_question' not in st.session_state:
    st.session_state.current_question = 0
if 'test_questions' not in st.session_state:
    st.session_state.test_questions = []
if 'answers' not in st.session_state:
    st.session_state.answers = []


# Helper functions
def check_table_exists(table_name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    tables = [table[0] for table in cursor.fetchall()]
    cursor.close()
    return table_name in tables


def get_available_tests():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tests_available")
    tests = cursor.fetchall()
    cursor.close()
    return tests


def get_test_results(test_name):
    conn = get_connection()
    cursor = conn.cursor()
    test_ans_table = f"{test_name.lower()}_ans"

    if check_table_exists(test_ans_table):
        try:
            cursor.execute(f"SELECT std_nm, marks FROM {test_ans_table}")
            results = cursor.fetchall()
            cursor.close()
            return results
        except Exception as e:
            st.error(f"Error fetching test results: {e}")
            cursor.close()
            return []
    else:
        cursor.close()
        return []


def user_already_answered_test(username, test_name):
    conn = get_connection()
    cursor = conn.cursor()
    # Use the sanitized version of the test name for the _ans table
    test_ans_table = f"{test_name.lower()}_ans"

    if check_table_exists(test_ans_table):
        try:
            cursor.execute(f"SELECT std_nm FROM {test_ans_table} WHERE std_nm = %s", (username,))
            result = cursor.fetchone()
            cursor.close()
            return result is not None
        except Exception as e:
            st.error(f"Error checking test answers: {e}")
            cursor.close()
            return False
    else:
        cursor.close()
        return False


def authenticate_user(username, password, user_type):
    conn = get_connection()
    cursor = conn.cursor()

    if user_type == "teacher":
        if username == "admin" and password == 2022:
            return True
        return False
    else:  # student
        cursor.execute("SELECT * FROM accounts WHERE name = %s AND pass = %s", (username, password))
        result = cursor.fetchone()
        cursor.close()
        return result is not None


def create_account(username, password):
    conn = get_connection()
    cursor = conn.cursor()

    # Check if account already exists
    cursor.execute("SELECT * FROM accounts WHERE name = %s AND pass = %s", (username, password))
    if cursor.fetchone():
        cursor.close()
        return False, "Account already exists"

    # Create new account
    try:
        cursor.execute("INSERT INTO accounts (name, pass) VALUES (%s, %s)", (username, password))
        conn.commit()
        cursor.close()
        return True, "Account created successfully"
    except Exception as e:
        conn.rollback()
        cursor.close()
        return False, f"Error creating account: {e}"


def get_test_questions(test_name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {test_name} ORDER BY Q_no")
    questions = cursor.fetchall()
    cursor.close()
    return questions


def submit_test_answers(username, test_name, answers, questions):
    conn = get_connection()
    cursor = conn.cursor()
    # Use the sanitized version of the test name for the _ans table
    test_ans_table = f"{test_name.lower()}_ans"

    # Calculate score
    score = 0
    for i, question in enumerate(questions):
        if i < len(answers) and answers[i] == question[6]:  # Check if answer matches correct_ansr
            score += 1

    # Create answer table if it doesn't exist
    if not check_table_exists(test_ans_table):
        try:
            cursor.execute(f"CREATE TABLE {test_ans_table} (std_nm CHAR(100), marks INT)")
        except Exception as e:
            st.error(f"Error creating answer table: {e}")
            conn.rollback()
            cursor.close()
            return 0, len(questions)

    # Insert score
    try:
        cursor.execute(f"INSERT INTO {test_ans_table} (std_nm, marks) VALUES (%s, %s)", (username, score))
        conn.commit()
    except Exception as e:
        st.error(f"Error recording test score: {e}")
        conn.rollback()

    cursor.close()
    return score, len(questions)


def create_new_test(test_name, questions_data):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Sanitize test name for MySQL (remove special characters and spaces)
        sanitized_test_name = ''.join(e for e in test_name if e.isalnum() or e == '_')

        # Ensure the name starts with a letter
        if not sanitized_test_name[0].isalpha():
            sanitized_test_name = 'test_' + sanitized_test_name

        # Check if test name is empty after sanitization
        if not sanitized_test_name:
            return False, "Test name must contain at least one letter or number"

        # Check if test name already exists
        if check_table_exists(sanitized_test_name):
            cursor.close()
            return False, "Test name already exists"

        # Get next serial number
        cursor.execute("SELECT COUNT(*) FROM tests_available")
        serial_no = cursor.fetchone()[0] + 1

        # Add to available tests (store original name for display but use sanitized for table)
        cursor.execute("INSERT INTO tests_available (s_no, test_name) VALUES (%s, %s)",
                       (serial_no, sanitized_test_name))

        # Create test table
        create_table_sql = f"""
            CREATE TABLE {sanitized_test_name} (
                Q_no INT, 
                quest VARCHAR(200), 
                o1 VARCHAR(150), 
                o2 VARCHAR(150), 
                o3 VARCHAR(150), 
                o4 VARCHAR(150), 
                correct_ansr INT
            )
        """
        cursor.execute(create_table_sql)

        # Insert questions
        for i, q in enumerate(questions_data):
            cursor.execute(
                f"INSERT INTO {sanitized_test_name} (Q_no, quest, o1, o2, o3, o4, correct_ansr) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (i + 1, q['question'], q['options'][0], q['options'][1], q['options'][2], q['options'][3], q['correct'])
            )

        conn.commit()
        cursor.close()

        # If test name was sanitized, inform the user
        if sanitized_test_name != test_name:
            return True, f"Test created successfully as '{sanitized_test_name}' (original name was modified to meet database requirements)"
        else:
            return True, "Test created successfully"

    except Exception as e:
        conn.rollback()
        cursor.close()
        return False, f"Error creating test: {e}"


# UI Components
def render_header():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("📝 Quiz Management System")
    with col2:
        if st.session_state.logged_in:
            st.write(f"Logged in as: **{st.session_state.username}** ({st.session_state.user_type})")
            if st.button("Logout"):
                for key in st.session_state.keys():
                    del st.session_state[key]
                st.rerun()


def render_navigation():
    if st.session_state.logged_in:
        cols = st.columns(4)
        with cols[0]:
            if st.button("Home", use_container_width=True):
                st.session_state.current_page = "home"
                st.rerun()

        if st.session_state.user_type == "student":
            with cols[1]:
                if st.button("Available Tests", use_container_width=True):
                    st.session_state.current_page = "tests"
                    st.rerun()

        if st.session_state.user_type == "teacher":
            with cols[1]:
                if st.button("Create Test", use_container_width=True):
                    st.session_state.current_page = "create_test"
                    st.rerun()
            with cols[2]:
                if st.button("View Tests & Results", use_container_width=True):
                    st.session_state.current_page = "view_tests"
                    st.rerun()


def render_home_page():
    st.header("Welcome to Quiz Management System")
    st.write("This system allows teachers to create tests and students to take them.")

    if not st.session_state.logged_in:
        tab1, tab2 = st.tabs(["Login", "Create Account"])

        with tab1:
            with st.form("login_form"):
                st.subheader("Login")
                user_type = st.radio("Login as:", ["Student", "Teacher"])
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Login")

                if submit:
                    if not username or not password:
                        st.error("Please enter both username and password")
                    else:
                        user_type = user_type.lower()
                        try:
                            password_num = int(password)
                            if authenticate_user(username, password_num, user_type):
                                st.session_state.logged_in = True
                                st.session_state.username = username
                                st.session_state.user_type = user_type
                                st.success(f"Logged in successfully as {user_type}")
                                st.rerun()
                            else:
                                st.error("Invalid credentials")
                        except ValueError:
                            st.error("Password must be a number")

        with tab2:
            with st.form("register_form"):
                st.subheader("Create Account")
                new_username = st.text_input("Username")
                new_password = st.text_input("Password (numbers only)", type="password")
                submit_reg = st.form_submit_button("Create Account")

                if submit_reg:
                    if not new_username or not new_password:
                        st.error("Please enter both username and password")
                    else:
                        try:
                            password_num = int(new_password)
                            success, message = create_account(new_username, password_num)
                            if success:
                                st.success(message)
                                st.session_state.logged_in = True
                                st.session_state.username = new_username
                                st.session_state.user_type = "student"
                                st.rerun()
                            else:
                                st.error(message)
                        except ValueError:
                            st.error("Password must be a number")
    else:
        if st.session_state.user_type == "student":
            st.info("Navigate to Available Tests to take quizzes")
        else:
            st.info("Navigate to Create Test to make new quizzes or View Tests to see existing ones")


def render_tests_page():
    st.header("Available Tests")

    tests = get_available_tests()
    if not tests:
        st.warning("No tests available")
        return

    test_options = [f"{test[0]}. {test[1]}" for test in tests]
    selected_test_index = st.selectbox("Select a test to take:", range(len(test_options)),
                                       format_func=lambda i: test_options[i])

    if selected_test_index is not None:
        selected_test = tests[selected_test_index][1]

        # Check if user already answered this test
        if user_already_answered_test(st.session_state.username, selected_test):
            st.warning(f"You have already answered the test: {selected_test}")
        else:
            if st.button(f"Take Test: {selected_test}"):
                st.session_state.selected_test = selected_test
                st.session_state.test_questions = get_test_questions(selected_test)
                st.session_state.current_question = 0
                st.session_state.answers = []
                st.session_state.current_page = "take_test"
                st.rerun()


def render_take_test_page():
    if not st.session_state.selected_test or not st.session_state.test_questions:
        st.error("No test selected")
        return

    st.header(f"Taking Test: {st.session_state.selected_test}")

    questions = st.session_state.test_questions
    current_q = st.session_state.current_question

    # Display progress
    progress_text = f"Question {current_q + 1} of {len(questions)}"
    st.progress((current_q + 1) / len(questions))
    st.write(progress_text)

    # Display current question
    q = questions[current_q]
    st.subheader(f"Q{q[0]}: {q[1]}")

    options = [q[2], q[3], q[4], q[5]]
    selected_option = st.radio("Select your answer:", range(1, 5),
                               format_func=lambda i: f"{i}. {options[i - 1]}")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Previous") and current_q > 0:
            if len(st.session_state.answers) > current_q:
                # Save current answer before moving
                st.session_state.answers[current_q] = selected_option
            st.session_state.current_question -= 1
            st.rerun()

    with col2:
        if current_q < len(questions) - 1:
            next_button = st.button("Next")
            if next_button:
                # Save answer
                if len(st.session_state.answers) <= current_q:
                    st.session_state.answers.append(selected_option)
                else:
                    st.session_state.answers[current_q] = selected_option
                st.session_state.current_question += 1
                st.rerun()
        else:
            if st.button("Submit Test"):
                # Save final answer
                if len(st.session_state.answers) <= current_q:
                    st.session_state.answers.append(selected_option)
                else:
                    st.session_state.answers[current_q] = selected_option

                # Submit test
                score, total = submit_test_answers(
                    st.session_state.username,
                    st.session_state.selected_test,
                    st.session_state.answers,
                    st.session_state.test_questions
                )

                st.session_state.current_page = "test_results"
                st.session_state.test_score = score
                st.session_state.test_total = total
                st.rerun()


def render_test_results_page():
    st.header("Test Results")
    st.subheader(f"Test: {st.session_state.selected_test}")

    score = st.session_state.test_score
    total = st.session_state.test_total

    st.markdown(f"""
    ### Your Score: {score}/{total}
    Percentage: {score / total * 100:.1f}%
    """)

    if st.button("Return to Available Tests"):
        st.session_state.current_page = "tests"
        st.rerun()


def render_create_test_page():
    st.header("Create New Test")

    # Help information for test naming
    st.info(
        "📌 Test names can only contain letters, numbers, and underscores. Special characters and spaces will be automatically removed.")

    with st.form("create_test_form"):
        test_name = st.text_input("Test Name")
        sanitized_preview = ''.join(e for e in test_name if e.isalnum() or e == '_')
        if sanitized_preview and not sanitized_preview[0].isalpha():
            sanitized_preview = 'test_' + sanitized_preview

        if test_name and test_name != sanitized_preview:
            st.warning(f"Your test name will be stored as: '{sanitized_preview}'")

        num_questions = st.number_input("Number of Questions", min_value=1, max_value=50, value=5)

        # Generate dynamic form for questions
        questions_data = []
        for i in range(int(num_questions)):
            st.subheader(f"Question {i + 1}")
            question = st.text_input(f"Question {i + 1}", key=f"q_{i}")
            options = [
                st.text_input(f"Option 1", key=f"q_{i}_o1"),
                st.text_input(f"Option 2", key=f"q_{i}_o2"),
                st.text_input(f"Option 3", key=f"q_{i}_o3"),
                st.text_input(f"Option 4", key=f"q_{i}_o4")
            ]
            correct = st.selectbox(f"Correct Answer", [1, 2, 3, 4], key=f"q_{i}_correct")

            questions_data.append({
                'question': question,
                'options': options,
                'correct': correct
            })

        submit = st.form_submit_button("Create Test")

        if submit:
            if not test_name:
                st.error("Please enter a test name")
            elif not all(q['question'] and all(q['options']) for q in questions_data):
                st.error("Please fill in all questions and options")
            else:
                success, message = create_new_test(test_name, questions_data)
                if success:
                    st.success(message)
                    st.session_state.current_page = "view_tests"
                    st.rerun()
                else:
                    st.error(message)


def render_view_tests_page():
    st.header("View Tests")

    tests = get_available_tests()
    if not tests:
        st.warning("No tests available")
        return

    # Convert to DataFrame for better display
    tests_df = pd.DataFrame(tests, columns=["Test ID", "Test Name"])
    st.dataframe(tests_df, use_container_width=True)

    # Select test to view details
    test_options = [f"{test[0]}. {test[1]}" for test in tests]
    selected_test_index = st.selectbox("Select a test to view details:",
                                       range(len(test_options)),
                                       format_func=lambda i: test_options[i])

    if selected_test_index is not None:
        selected_test = tests[selected_test_index][1]

        # Create tabs for Questions and Student Results
        tab1, tab2 = st.tabs(["Questions", "Student Results"])

        with tab1:
            st.subheader(f"Questions for: {selected_test}")
            questions = get_test_questions(selected_test)
            if questions:
                for i, q in enumerate(questions):
                    with st.expander(f"Question {q[0]}: {q[1]}"):
                        st.write(f"Option 1: {q[2]}")
                        st.write(f"Option 2: {q[3]}")
                        st.write(f"Option 3: {q[4]}")
                        st.write(f"Option 4: {q[5]}")
                        st.write(f"Correct Answer: Option {q[6]}")
            else:
                st.warning("No questions found for this test")

        with tab2:
            st.subheader(f"Student Results for: {selected_test}")

            # Check if answer table exists
            test_ans_table = f"{selected_test.lower()}_ans"
            if check_table_exists(test_ans_table):
                # Get student results
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(f"SELECT std_nm, marks FROM {test_ans_table}")
                results = cursor.fetchall()
                cursor.close()

                if results:
                    # Get total number of questions
                    cursor = conn.cursor()
                    cursor.execute(f"SELECT COUNT(*) FROM {selected_test}")
                    total_questions = cursor.fetchone()[0]
                    cursor.close()

                    # Create DataFrame with percentage
                    results_df = pd.DataFrame(results, columns=["Student Name", "Score"])
                    results_df["Total Questions"] = total_questions
                    results_df["Percentage"] = (results_df["Score"] / total_questions * 100).round(2).astype(str) + '%'

                    # Display with sorting options
                    st.dataframe(results_df, use_container_width=True,
                                 hide_index=True)

                    # Download results button
                    csv = results_df.to_csv(index=False)
                    st.download_button(
                        label="Download Results as CSV",
                        data=csv,
                        file_name=f"{selected_test}_results.csv",
                        mime="text/csv"
                    )

                    # Statistics
                    st.subheader("Test Statistics")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Attempts", len(results))
                    with col2:
                        avg_score = results_df["Score"].mean()
                        st.metric("Average Score", f"{avg_score:.2f}/{total_questions}")
                    with col3:
                        avg_percentage = results_df["Score"].mean() / total_questions * 100
                        st.metric("Average Percentage", f"{avg_percentage:.2f}%")

                    # Score distribution
                    score_counts = results_df["Score"].value_counts().sort_index()
                    if not score_counts.empty:
                        st.subheader("Score Distribution")
                        st.bar_chart(score_counts)
                else:
                    st.info("No students have attempted this test yet")
            else:
                st.info("No students have attempted this test yet")


# Main App Logic
def main():
    render_header()
    st.divider()
    render_navigation()

    # Render the current page
    if st.session_state.current_page == "home":
        render_home_page()
    elif st.session_state.current_page == "tests" and st.session_state.logged_in:
        render_tests_page()
    elif st.session_state.current_page == "take_test" and st.session_state.logged_in:
        render_take_test_page()
    elif st.session_state.current_page == "test_results" and st.session_state.logged_in:
        render_test_results_page()
    elif st.session_state.current_page == "create_test" and st.session_state.logged_in and st.session_state.user_type == "teacher":
        render_create_test_page()
    elif st.session_state.current_page == "view_tests" and st.session_state.logged_in and st.session_state.user_type == "teacher":
        render_view_tests_page()
    else:
        render_home_page()


if __name__ == "__main__":
    main()
