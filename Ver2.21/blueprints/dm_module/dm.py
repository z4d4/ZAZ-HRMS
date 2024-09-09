from flask import Flask, Blueprint, render_template, request, redirect, url_for, session, flash
import sqlite3
import os

dm_module = Blueprint("dm_module", __name__, template_folder="templates")


# Function to disciplinary data for a specific user
def get_user_disciplinary_data(user_id):
    db_path = 'hrmdb.db'
    con = sqlite3.connect(db_path)
    cursor = con.cursor()
    cursor.execute("SELECT * FROM 'Disciplinary Record' WHERE User_ID = ?", (user_id,))
    disciplinary_data = cursor.fetchall()
    con.close()
    return disciplinary_data

# Function to get disciplinary data for admins by department
def get_department_disciplinary_data(department):
    db_path = 'hrmdb.db'
    con = sqlite3.connect(db_path)
    cursor = con.cursor()
    cursor.execute("""
        SELECT dr.Disciplinary_ID, ei.Name, ei.User_name, dr.Disciplinary_Case, dr.Type, dr.Penal_Code
        FROM 'Disciplinary Record' dr
        JOIN 'Employee Information' ei ON dr.User_ID = ei.User_ID, dr.Employee_Name = ei.Name
        WHERE ei.Department = ?
    """, (department,))
    dr_data = cursor.fetchall()
    con.close()
    print(f"Displinary data retrieved for department: {dr_data}")  # Debugging info
    return dr_data

# Route for Disciplinary Management
@dm_module.route('/disciplinary_management', methods=['GET', 'POST'])
def dm():
    user_details = session['user']
    if 'user' not in session:
        return redirect(url_for('login'))

    role = user_details[12]  # Assuming 'Role' is the 13th column in 'Employee Information' table
    department = user_details[11]  # Assuming 'Department' is the 12th column in 'Employee Information' table

    if 'Manager' in role:
        # Manager/Admin view
        dr_data = get_department_disciplinary_data(department)

        if request.method == 'POST':
            disciplinary_id = request.form.get('disciplinary_id')
            status = request.form.get('report_status')
            user_id = request.form.get('user_id')

            print(f"Form submitted with action: {report_status}, Disciplinary ID: {disciplinary_id}, User ID: {user_id}")  # Debugging


            if report_status == 'Reject' and status:
                update_report_status(disciplinary_id, 'Rejected', status)
                create_notification(user_id, f"Your report has been rejected. Status: {report_status}")
                flash('Report rejected successfully!')
            elif report_status == 'Processing':
                update_report_status(disciplinary_id, 'Processing')
                create_notification(user_id, "Your report is now in process.")
                flash('Report accepted!')
            else:
                flash('Invalid action')

            return redirect(url_for('disciplinary_management'))

        return render_template('dm_admin.html', user_details=user_details, dr_data=dr_data)

    else:
        # Employee view
        user_id = user_details[0]  # Assuming 'User_ID' is the first column in 'Employee Information' table
        dr_data = get_user_disciplinary_data(user_id)

        if request.method == 'POST':
            if 'submit_report' in request.form:
                report_details = request.form.get('report_details')

                submit_a_report(user_id, report_details)

                # Notify admin of new report
                admin_id = get_admin_id(department)
                create_notification(admin_id, "A new report has been submitted by an employee.")

                return redirect(url_for('disciplinary_management'))

            elif 'cancel_report' in request.form:
                report_id = request.form.get('report_id')
                cancel_report(report_id)
                return redirect(url_for('disciplinary_management'))

        notifications = fetch_notifications(user_id)
        return render_template('dm_user.html', user_details=user_details, dr_data=dr_data, notifications=notifications)