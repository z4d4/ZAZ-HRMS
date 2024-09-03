from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for session management

# Define a route for the home page
@app.route('/home')
def home():
    return render_template('home.html')

# Function to check user credentials and fetch user details
def validate(username, password):
    db_path = 'hrmdb.db'  # Update this path as necessary
    if not os.path.exists(db_path):
        print(f"Database file not found at {db_path}")
        return None
    con = sqlite3.connect(db_path)
    cursor = con.cursor()
    cursor.execute("SELECT * FROM 'Employee Information' WHERE User_name = ? AND Pass_word = ?", (username, password))
    result = cursor.fetchone()
    con.close()
    if result:
        return result  # Return the user details
    else:
        return None

# Function to fetch unread notifications for a user
def fetch_notifications(user_id):
    db_path = 'hrmdb.db'
    con = sqlite3.connect(db_path)
    cursor = con.cursor()
    cursor.execute("SELECT * FROM 'Notifications' WHERE User_ID = ? AND Is_Read = 0 ORDER BY Created_At DESC", (user_id,))
    notifications = cursor.fetchall()
    con.close()
    return notifications

# Function to create a notification for a user
def create_notification(user_id, message):
    db_path = 'hrmdb.db'
    con = sqlite3.connect(db_path)
    cursor = con.cursor()
    cursor.execute("INSERT INTO 'Notifications' (User_ID, Message) VALUES (?, ?)", (user_id, message))
    con.commit()
    con.close()

# Route for the login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user_details = validate(username, password)
        if user_details:
            session['user'] = user_details  # Store user details in session
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid Credentials! Please try again."

    return render_template('login.html', error=error)

# Route for logout
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# Route for the dashboard (post-login)
@app.route('/dashboard')
def dashboard():
    if 'user' in session:
        user_details = session['user']
        notifications = fetch_notifications(user_details[0])
        return render_template('dashboard.html', user_details=user_details, notifications=notifications)
    else:
        return redirect(url_for('login'))

# Function to get leave data for a specific user
def get_user_leave_data(user_id):
    db_path = 'hrmdb.db'
    con = sqlite3.connect(db_path)
    cursor = con.cursor()
    cursor.execute("SELECT * FROM 'Leave Applications' WHERE User_ID = ?", (user_id,))
    leave_data = cursor.fetchall()
    con.close()
    return leave_data

# Function to get leave data for admins by department
def get_department_leave_data(department):
    db_path = 'hrmdb.db'
    con = sqlite3.connect(db_path)
    cursor = con.cursor()
    cursor.execute("""
        SELECT la.Leave_ID, la.User_ID, la.Start_Date, la.End_Date, la.Status, la.Leave_Reason, la.Reason
        FROM 'Leave Applications' la
        JOIN 'Employee Information' ei ON la.User_ID = ei.User_ID
        WHERE ei.Department = ?
    """, (department,))
    leave_data = cursor.fetchall()
    con.close()
    return leave_data

# Route for Leave Application
@app.route('/leave_application', methods=['GET', 'POST'])
def leave_application():
    if 'user' not in session:
        return redirect(url_for('login'))

    user_details = session['user']
    role = user_details[12]  # Assuming 'Role' is the 13th column in 'Employee Information' table
    department = user_details[11]  # Assuming 'Department' is the 12th column in 'Employee Information' table

    if 'Manager' in role:
        # Admin view
        leave_data = get_department_leave_data(department)
        if request.method == 'POST':
            leave_id = request.form.get('leave_id')
            action = request.form.get('action')
            reason = request.form.get('reason') if 'reason' in request.form else None
            if action == 'Reject' and not reason:
                flash('Please provide a reason for rejection.')
                return redirect(url_for('leave_application'))

            # Check if the 'Confirm' button was clicked after entering the reason
            if request.form.get('confirm_reject') == 'Confirm' and reason:
                # Process rejection with reason
                update_leave_status(leave_id, 'Rejected', reason)

                # Notify employee of rejection
                user_id = request.form.get('user_id')
                create_notification(user_id, f"Your leave request has been rejected. Reason: {reason}")

            elif action == 'Approve':
                # Process approval
                update_leave_status(leave_id, 'Approved')

                # Notify employee of approval
                user_id = request.form.get('user_id')
                create_notification(user_id, "Your leave request has been approved.")
            else:
                # If not confirmed or invalid action, do nothing
                flash('Please confirm your action with a valid reason for rejection.')
                return redirect(url_for('leave_application'))

        return render_template('leave_application_admin.html', user_details=user_details, leave_data=leave_data)
    else:
        # Employee view
        user_id = user_details[0]  # Assuming 'User_ID' is the first column in 'Employee Information' table
        leave_data = get_user_leave_data(user_id)
        if request.method == 'POST':
            if 'apply_leave' in request.form:
                start_date = request.form.get('start_date')
                end_date = request.form.get('end_date')
                leave_reason = request.form.get('leave_reason')
                apply_for_leave(user_id, start_date, end_date, leave_reason)

                # Notify admin of new leave request
                admin_id = get_admin_id(department)
                create_notification(admin_id, "A new leave request has been submitted by an employee.")

                return redirect(url_for('leave_application'))
            elif 'cancel_leave' in request.form:
                leave_id = request.form.get('leave_id')
                cancel_leave(leave_id)
                return redirect(url_for('leave_application'))

        notifications = fetch_notifications(user_id)
        return render_template('leave_application_user.html', user_details=user_details, leave_data=leave_data, notifications=notifications)

# Function to update leave status for admin
def update_leave_status(leave_id, status, reason=None):
    db_path = 'hrmdb.db'
    con = sqlite3.connect(db_path)
    cursor = con.cursor()
    if reason:
        cursor.execute("UPDATE 'Leave Applications' SET Status = ?, Reason = ? WHERE Leave_ID = ?", (status, reason, leave_id))
    else:
        cursor.execute("UPDATE 'Leave Applications' SET Status = ? WHERE Leave_ID = ?", (status, leave_id))
    con.commit()
    con.close()

# Function to apply for leave for user
def apply_for_leave(user_id, start_date, end_date, leave_reason):
    db_path = 'hrmdb.db'
    con = sqlite3.connect(db_path)
    cursor = con.cursor()
    cursor.execute(
        "INSERT INTO 'Leave Applications' (User_ID, Start_Date, End_Date, Status, Leave_Reason) VALUES (?, ?, ?, 'Submitted, Pending Review', ?)", 
        (user_id, start_date, end_date, leave_reason)
    )
    con.commit()
    con.close()

# Function to cancel leave for user
def cancel_leave(leave_id):
    db_path = 'hrmdb.db'
    con = sqlite3.connect(db_path)
    cursor = con.cursor()
    cursor.execute("DELETE FROM 'Leave Applications' WHERE Leave_ID = ?", (leave_id,))
    con.commit()
    con.close()

# Function to get the admin ID for a specific department
def get_admin_id(department):
    db_path = 'hrmdb.db'
    con = sqlite3.connect(db_path)
    cursor = con.cursor()
    cursor.execute("SELECT User_ID FROM 'Employee Information' WHERE Department = ? AND Role LIKE '%Manager%'", (department,))
    result = cursor.fetchone()
    con.close()
    return result[0] if result else None

if __name__ == '__main__':
    app.run(debug=True)
