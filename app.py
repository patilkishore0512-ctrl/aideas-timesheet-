import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, timedelta
import base64
import random
from PIL import Image
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO
from auth_systems import auth_wrapper, load_users
import urllib.parse

HOLIDAYS_2025 = {
    "01/01/2025": "New Year",
    "01/14/2025": "Makara sankranti",
    "02/26/2025": "Maha Shivaratri",
    "05/01/2025": "May Day",
    "08/15/2025": "Independence Day",
    "08/27/2025": "Ganesh Chaturthi",
    "09/05/2025": "Eid -E- Milad",
    "10/01/2025": "Ayudha Pooja",
    "10/02/2025": "Gandhi Jayanthi",
    "10/22/2025": "Deepavali",
    "12/25/2025": "Christmas"
}

def process_signature(uploaded_file):
    if uploaded_file is not None:
        image_bytes = uploaded_file.read()
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode != 'RGB':
            image = image.convert('RGB')
        max_size = (200, 100)
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        return img_byte_arr
    return None

def process_screenshots(uploaded_files):
    processed_images = []
    if uploaded_files:
        for uploaded_file in uploaded_files:
            image_bytes = uploaded_file.read()
            image = Image.open(io.BytesIO(image_bytes))
            if image.mode != 'RGB':
                image = image.convert('RGB')
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG', quality=95)
            processed_images.append(img_byte_arr.getvalue())
    return processed_images

def generate_random_time():
    minutes = random.randint(0, 70)
    hours = 9
    total_minutes = hours * 60 + minutes
    work_duration = random.randint(540, 570)
    out_time_minutes = total_minutes + work_duration
    in_time = f"{str(total_minutes // 60).zfill(2)}:{str(total_minutes % 60).zfill(2)}"
    out_time = f"{str(out_time_minutes // 60).zfill(2)}:{str(out_time_minutes % 60).zfill(2)}"
    hours_worked = f"{work_duration // 60}:{str(work_duration % 60).zfill(2)}"
    return in_time, out_time, hours_worked

def get_weekends_for_month(year, month):
    num_days = calendar.monthrange(year, month)[1]
    weekends = []
    for day in range(1, num_days + 1):
        current_date = datetime(year, month, day)
        if current_date.weekday() >= 5:
            weekends.append(current_date.strftime("%m/%d/%Y"))
    return weekends

def get_dates_for_month(year, month):
    num_days = calendar.monthrange(year, month)[1]
    dates = []
    weekends = get_weekends_for_month(year, month)
    for day in range(1, num_days + 1):
        date_str = datetime(year, month, day).strftime("%m/%d/%Y")
        if date_str not in weekends and date_str not in HOLIDAYS_2025:
            dates.append(date_str)
    return dates

def create_timesheet(year, month, employee_data, projects, leave_dates, wfh_dates):
    num_days = calendar.monthrange(year, month)[1]
    weekends = get_weekends_for_month(year, month)
    dates = [datetime(year, month, day) for day in range(1, num_days + 1)]
    timesheet_data = []
    
    default_projects = "\n".join(f"{i+1}. {project}" for i, project in enumerate(projects))
    
    for date in dates:
        date_str = date.strftime("%m/%d/%Y")
        time_in, time_out, hours = ("9:00", "18:00", "9:00")
        work_location = "WFO"  # Default to Work From Office
        
        # Determine work location
        if date_str in wfh_dates:
            work_location = "WFH"
        
        if date_str not in weekends and date_str not in HOLIDAYS_2025 and date_str not in leave_dates:
            time_in, time_out, hours = generate_random_time()
        
        entry = {
            "Date": date_str,
            "Time-In": time_in,
            "Time-out": time_out,
            "Hours": hours,
            "WFO/WFH": work_location,
            "Job Description": default_projects
        }
        
        if date_str in HOLIDAYS_2025:
            entry.update({
                "WFO/WFH": "",
                "Job Description": HOLIDAYS_2025[date_str],
                "Time-In": "9:00",
                "Time-out": "18:00",
                "Hours": "9:00"
            })
        elif date_str in leave_dates:
            leave_type = leave_dates[date_str]
            entry.update({
                "WFO/WFH": "",
                "Job Description": leave_type,
                "Time-In": "9:00",
                "Time-out": "18:00",
                "Hours": "9:00"
            })
        elif date_str in weekends:
            entry.update({
                "WFO/WFH": "",
                "Job Description": "Week Off",
                "Time-In": "9:00",
                "Time-out": "18:00",
                "Hours": "9:00"
            })
            
        timesheet_data.append(entry)
    
    return pd.DataFrame(timesheet_data)

def create_pdf(df, employee_data, month_year, employee_signature=None, screenshots=None):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    # Logo
    logo_path = "aideas_logo.png"
    if logo_path:
        logo = RLImage(logo_path, width=2*inch, height=0.8*inch)
        story.append(logo)
    story.append(Spacer(1, 20))
    
    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, spaceAfter=20, alignment=1)
    title = Paragraph(f"Timesheet - {calendar.month_name[month_year[0]]} {month_year[1]}", title_style)
    story.append(title)
    
    # Employee Info
    info_style = ParagraphStyle('Info', parent=styles['Normal'], fontSize=10, spaceAfter=3)
    employee_info = [
        f"Employee Name: {employee_data['name']}",
        f"Employee ID: {employee_data['id']}",
        f"Location: {employee_data['location']}",
        f"Manager: {employee_data['manager']}"
    ]
    for info in employee_info:
        story.append(Paragraph(info, info_style))
    
    story.append(Spacer(1, 30))

    # Timesheet Table
    table_data = [df.columns.tolist()]
    para_style = ParagraphStyle('CustomBody', parent=styles['Normal'], fontSize=8, leading=10, spaceBefore=0, spaceAfter=0, leftIndent=0, rightIndent=0)
    
    for _, row in df.iterrows():
        processed_row = []
        for col in df.columns:
            cell_value = str(row[col])
            if col == 'Job Description':
                cell_value = Paragraph(cell_value.replace('\n', '<br/>'), para_style)
            processed_row.append(cell_value)
        table_data.append(processed_row)
    
    col_widths = [1.0*inch, 0.8*inch, 0.8*inch, 0.7*inch, 0.7*inch, 3.5*inch]
    table = Table(table_data, repeatRows=1, colWidths=col_widths)
    
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADING', (0, 0), (-1, 0), 8),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (5, 0), (5, -1), 'LEFT'),
        ('VALIGN', (5, 0), (5, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ])
    
    # Apply different background colors for different row types
    for row_idx, row in enumerate(table_data[1:], 1):
        job_desc = str(row[-1])
        wfo_wfh = str(row[4])  # WFO/WFH column
        
        if any(holiday in job_desc for holiday in HOLIDAYS_2025.values()):
            table_style.add('BACKGROUND', (0, row_idx), (-1, row_idx), colors.Color(1, 0.9, 0.8))
        elif 'Week Off' in job_desc:
            table_style.add('BACKGROUND', (0, row_idx), (-1, row_idx), colors.Color(1, 0.98, 0.9))
        elif 'Sick Leave' in job_desc or 'Earned Leave' in job_desc:
            table_style.add('BACKGROUND', (0, row_idx), (-1, row_idx), colors.Color(0.784, 0.902, 0.788))
        elif wfo_wfh == 'WFH':
            # Light blue background for WFH days
            table_style.add('BACKGROUND', (0, row_idx), (-1, row_idx), colors.Color(0.9, 0.95, 1.0))
    
    table.setStyle(table_style)
    story.append(table)
    
    # Employee Signature
    story.append(Spacer(1, 30))
    if employee_signature:
        sig_img = RLImage(io.BytesIO(employee_signature), width=1.5*inch, height=0.75*inch)
        signature_table = Table([["Employee Signature:", sig_img]], colWidths=[2*inch, 2*inch])
    else:
        signature_table = Table([["Employee Signature:", "_________________"]], colWidths=[2*inch, 2*inch])
    
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONT', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))
    story.append(signature_table)

    # Screenshots
    if screenshots:
        story.append(PageBreak())
        story.append(Paragraph("SAP Screenshots", title_style))
        story.append(Spacer(1, 20))
        for screenshot in screenshots:
            img = Image.open(io.BytesIO(screenshot))
            width, height = img.size
            aspect_ratio = width / height
            max_width = 500  # Fit within A4 width (595 points)
            max_height = max_width / aspect_ratio
            if max_height > 700:  # Limit height to fit A4 (842 points)
                max_height = 700
                max_width = max_height * aspect_ratio
            img = RLImage(io.BytesIO(screenshot), width=max_width, height=max_height, hAlign='CENTER')
            story.append(img)
            story.append(Spacer(1, 20))

    doc.build(story)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data

def style_dataframe(df):
    def highlight_rows(row):
        job_desc = str(row['Job Description'])
        wfo_wfh = str(row['WFO/WFH'])
        
        if any(holiday in job_desc for holiday in HOLIDAYS_2025.values()):
            return ['background-color: #FFE0B2'] * len(row)
        elif 'Week Off' in job_desc:
            return ['background-color: #FFF9C4'] * len(row)
        elif 'Sick Leave' in job_desc or 'Earned Leave' in job_desc:
            return ['background-color: #C8E6C9'] * len(row)
        elif wfo_wfh == 'WFH':
            return ['background-color: #E3F2FD'] * len(row)  # Light blue for WFH
        return [''] * len(row)
    
    styled_df = df.style.apply(highlight_rows, axis=1)
    return styled_df

def create_outlook_url(recipient_email, subject, body):
    subject = urllib.parse.quote(subject)
    body = urllib.parse.quote(body)
    cc = urllib.parse.quote("murali@aideasengineering.com; amrutha@aideasengineering.com")
    outlook_url = f"mailto:{recipient_email}?subject={subject}&cc={cc}&body={body}"
    return outlook_url

def save_and_open_email(recipient_email, month_year, employee_data, df, has_screenshots=False):
    working_days, sick_leaves, earned_leaves, wfh_days, wfo_days = calculate_metrics(df)
    subject = f"Aideas || Approval for Timesheet || {calendar.month_name[month_year[0]]}-{month_year[1]}"
    body = f"""Dear {employee_data['manager']},

As per above mentioned I am submitting my timesheet for {calendar.month_name[month_year[0]]} - {month_year[1]} and kindly request your approval.

Please find attached my completed timesheet{f" with screenshots" if has_screenshots else ""}. 

I have carefully recorded all my work hours, including:
1. Work From Office (WFO) days: {wfo_days} Days
2. Work From Home (WFH) days: {wfh_days} Days          
3. Sick Leave taken: {sick_leaves} Days
4. Earned Leave taken: {earned_leaves} Days

Total Working Days: {working_days} Days

I have ensured that all project work is accurately reflected in the timesheet."""
    outlook_url = create_outlook_url(recipient_email, subject, body)
    return outlook_url

def display_pdf(pdf_data):
    base64_pdf = base64.b64encode(pdf_data).decode('utf-8')
    st.markdown(f"""<embed src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></embed>""", unsafe_allow_html=True)

def calculate_metrics(df):
    working_days = len([row for _, row in df.iterrows() if row['Job Description'] not in ['Sick Leave', 'Earned Leave'] and 'Week Off' not in row['Job Description'] and row['Job Description'] not in HOLIDAYS_2025.values()])
    sick_leaves = len([row for _, row in df.iterrows() if row['Job Description'] == 'Sick Leave'])
    earned_leaves = len([row for _, row in df.iterrows() if row['Job Description'] == 'Earned Leave'])
    wfh_days = len([row for _, row in df.iterrows() if row['WFO/WFH'] == 'WFH'])
    wfo_days = len([row for _, row in df.iterrows() if row['WFO/WFH'] == 'WFO'])
    return working_days, sick_leaves, earned_leaves, wfh_days, wfo_days

def main():
    st.title("Aideas Timesheet Generator - 2025")
    
    # Initialize session state
    if 'timesheet_generated' not in st.session_state:
        st.session_state.timesheet_generated = False
    if 'timesheet_df' not in st.session_state:
        st.session_state.timesheet_df = None
    if 'screenshots' not in st.session_state:
        st.session_state.screenshots = []
    
    # Get current user's data
    try:
        users = load_users()
        current_user_id = st.session_state.current_user
        if current_user_id not in users:
            st.error("User does not exist in the system.")
            return
        current_user = users[current_user_id]
        if 'name' not in current_user:
            st.error("User profile is incomplete.")
            return
    except Exception as e:
        st.error("Error loading user data.")
        return
    
    # Employee Information
    st.header("Employee Information")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Employee Name", value=current_user.get('name', ''), disabled=True, key="main_emp_name")
        st.text_input("Employee ID", value=current_user_id, disabled=True, key="main_emp_id")
    location = "ABB Southfield"
    manager = "Nikhil M"
    with col2:
        st.text_input("Work Location", value=location, disabled=True, key="main_location")
        st.text_input("Manager", value=manager, disabled=True, key="main_manager")

    # Signature Upload
    st.header("Signature Upload")
    employee_signature = st.file_uploader("Upload Employee Signature", type=['png', 'jpg', 'jpeg'], key="signature_upload")
    if employee_signature:
        st.image(employee_signature, width=200)
    
    # SAP Screenshots
    st.header("SAP Screenshots")
    screenshot_files = st.file_uploader("Upload SAP Screenshots", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True, key="screenshot_upload")
    if screenshot_files:
        st.session_state.screenshots = process_screenshots(screenshot_files)
        st.write("Uploaded Screenshots:")
        for i, screenshot in enumerate(st.session_state.screenshots):
            st.image(Image.open(io.BytesIO(screenshot)), caption=f"Screenshot {i+1}", width=200)

    # Month Selection
    st.header("Select Month")
    month = st.selectbox("Month", range(1, 13), format_func=lambda x: calendar.month_name[x], key="month_select")
    st.write("### Calendar for Selected Month (2025)")
    cal = calendar.monthcalendar(2025, month)
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    df_calendar = pd.DataFrame(cal, columns=days)
    st.dataframe(df_calendar, hide_index=True)
    
    month_holidays = {date: holiday for date, holiday in HOLIDAYS_2025.items() if int(date.split('/')[0]) == month}
    if month_holidays:
        st.write("### Holidays this month:")
        for date, holiday in month_holidays.items():
            st.write(f"- {date}: {holiday}")
    
    # Work From Home Selection
    st.header("Work From Home Selection")
    show_wfh_section = st.checkbox("Select Work From Home Dates", key="show_wfh")
    wfh_dates = []
    if show_wfh_section:
        available_dates = get_dates_for_month(2025, month)
        wfh_dates = st.multiselect(
            "Select Work From Home Dates", 
            available_dates, 
            key="wfh_dates",
            help="Select multiple dates when you will work from home"
        )
        if wfh_dates:
            st.success(f"Selected {len(wfh_dates)} WFH days: {', '.join(wfh_dates)}")
    
    # Leave Selection
    st.header("Leave Selection")
    show_leave_section = st.checkbox("Add Leave Dates", key="show_leave")
    leave_dates = {}
    if show_leave_section:
        available_dates = get_dates_for_month(2025, month)
        # Remove WFH dates from available leave dates to avoid conflicts
        available_leave_dates = [date for date in available_dates if date not in wfh_dates]
        
        col1, col2 = st.columns(2)
        with col1:
            sick_leave_dates = st.multiselect("Select Sick Leave Dates", available_leave_dates, key="sick_leave")
            for date in sick_leave_dates:
                leave_dates[date] = "Sick Leave"
        with col2:
            earned_leave_dates = st.multiselect(
                "Select Earned Leave Dates", 
                [d for d in available_leave_dates if d not in sick_leave_dates], 
                key="earned_leave"
            )
            for date in earned_leave_dates:
                leave_dates[date] = "Earned Leave"

    # Project Descriptions
    st.header("Default Project Descriptions")
    projects = []
    num_projects = st.number_input("Number of Projects", min_value=1, max_value=10, value=1, key="num_projects")
    for i in range(num_projects):
        project = st.text_input(f"Project {i+1} Description", key=f"project_{i}")
        if project:
            projects.append(project)
    
    if st.button("Generate Timesheet", key="generate_btn"):
        if not projects:
            st.error("Please add at least one project description")
            return
        employee_data = {"name": current_user.get('name', ''), "id": current_user_id, "location": location, "manager": manager}
        st.session_state.timesheet_df = create_timesheet(2025, month, employee_data, projects, leave_dates, wfh_dates)
        st.session_state.timesheet_generated = True
        st.session_state.employee_data = employee_data
    
    if st.session_state.timesheet_generated and st.session_state.timesheet_df is not None:
        # Enhanced Metrics
        working_days, sick_leaves, earned_leaves, wfh_days, wfo_days = calculate_metrics(st.session_state.timesheet_df)
        
        # Display metrics in a more organized way
        st.header("Monthly Summary")
        metrics_col1, metrics_col2, metrics_col3, metrics_col4, metrics_col5 = st.columns(5)
        with metrics_col1:
            st.metric("Total Working Days", working_days)
        with metrics_col2:
            st.metric("WFO Days", wfo_days)
        with metrics_col3:
            st.metric("WFH Days", wfh_days)
        with metrics_col4:
            st.metric("Sick Leaves", sick_leaves)
        with metrics_col5:
            st.metric("Earned Leaves", earned_leaves)

        # Edit Job Descriptions
        st.header("Edit Daily Job Descriptions")
        st.write("You can modify job descriptions for specific dates below:")
        edited_df = st.session_state.timesheet_df.copy()
        for idx, row in edited_df.iterrows():
            if (row['Job Description'] not in HOLIDAYS_2025.values() and 
                row['Job Description'] != 'Week Off' and 
                row['Job Description'] not in ['Sick Leave', 'Earned Leave']):
                
                # Show work location info
                work_location = "🏠 Work From Home" if row['WFO/WFH'] == 'WFH' else "🏢 Work From Office"
                st.write(f"**Date: {row['Date']}** - {work_location}")
                
                try:
                    current_projects = row['Job Description'].split('\n')
                    current_projects = [p.split('. ')[1] if '. ' in p else p for p in current_projects if p.strip()]
                    default_values = [p for p in current_projects if p in projects] if current_projects else []
                    selected_projects = st.multiselect("Select projects for this day", projects, default=default_values, key=f"proj_{idx}")
                    if selected_projects or selected_projects == []:
                        new_description = "\n".join(f"{i+1}. {proj}" for i, proj in enumerate(selected_projects)) if selected_projects else ""
                        edited_df.at[idx, 'Job Description'] = new_description
                except Exception as e:
                    st.error(f"Error processing projects for {row['Date']}: {str(e)}")
                st.write("---")
        st.session_state.timesheet_df = edited_df

        # Generate PDF
        processed_emp_sig = process_signature(employee_signature) if employee_signature else None
        pdf_data = create_pdf(
            edited_df,
            st.session_state.employee_data,
            (month, 2025),
            processed_emp_sig,
            st.session_state.screenshots
        )
        
        # Display Timesheet with enhanced styling
        st.write("### Final Timesheet")
        st.write("**Legend:** 🟠 Holidays | 🟡 Weekends | 🟢 Leaves | 🔵 Work From Home | ⚪ Work From Office")
        styled_df = style_dataframe(edited_df)
        st.dataframe(styled_df, use_container_width=True)

        st.download_button(
            label="Download PDF",
            data=pdf_data,
            file_name=f"{st.session_state.employee_data['id']}_{st.session_state.employee_data['name'].replace(' ', '')}_{calendar.month_name[month].lower()}-{2025}.pdf",
            mime="application/pdf"
        )
        
        # Email Button
        if st.button("Generate Mail Template for Outlook", key="generate_mail"):
            outlook_url = save_and_open_email(
                "nikhil.m@in.abb.com",
                (month, 2025),
                st.session_state.employee_data,
                edited_df,
                has_screenshots=bool(st.session_state.screenshots)
            )
            st.markdown(f'<a href="{outlook_url}" target="_blank">Click to Open Outlook</a>', unsafe_allow_html=True)
            st.info("After Outlook opens, please manually attach the downloaded PDF.")

if __name__ == "__main__":
    auth_wrapper(main)