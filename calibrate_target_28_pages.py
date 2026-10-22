"""
calibrate_target_28_pages.py
Fine-tunes typography, table compactness, image dimensions, and page break distribution
to bring the document to the exact target range of 25–30 pages (aiming for 27–29 pages).
"""

with open('generate_full_project_report.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Body text line spacing & paragraph spacing
text = text.replace('para.paragraph_format.line_spacing = 1.15', 'para.paragraph_format.line_spacing = 1.12')
text = text.replace('r_bold.font.size = Pt(11)', 'r_bold.font.size = Pt(10.5)')
text = text.replace('r_text.font.size = Pt(11)', 'r_text.font.size = Pt(10.5)')
text = text.replace('para.paragraph_format.space_after = Pt(3.5)', 'para.paragraph_format.space_after = Pt(2.5)')

# 2. Heading spacing
text = text.replace('para.paragraph_format.space_before = Pt(16)', 'para.paragraph_format.space_before = Pt(10)')
text = text.replace('para.paragraph_format.space_after = Pt(8)', 'para.paragraph_format.space_after = Pt(3)')
text = text.replace('r.font.size = Pt(16)', 'r.font.size = Pt(14)')

text = text.replace('para.paragraph_format.space_before = Pt(12)', 'para.paragraph_format.space_before = Pt(8)')
text = text.replace('para.paragraph_format.space_after = Pt(4)', 'para.paragraph_format.space_after = Pt(2)')
text = text.replace('r.font.size = Pt(14)', 'r.font.size = Pt(12)')

text = text.replace('para.paragraph_format.space_before = Pt(8)', 'para.paragraph_format.space_before = Pt(6)')
text = text.replace('para.paragraph_format.space_after = Pt(2)', 'para.paragraph_format.space_after = Pt(1.5)')
text = text.replace('r.font.size = Pt(12)', 'r.font.size = Pt(11)')

# 3. Only keep page breaks before Section 4 (Architecture), Section 5 (Modules), Section 8 (Testing), and Section 13 (Appendices)
# Let all other sections flow naturally
text = text.replace('h1("3. Technology Stack and System Requirements")', 'h1("3. Technology Stack and System Requirements", page_break=False)')
text = text.replace('h1("6. Security and Safety Controls")', 'h1("6. Security and Safety Controls", page_break=False)')
text = text.replace('h1("9. Proposed AWS EC2 Deployment and Cost Considerations")', 'h1("9. Proposed AWS EC2 Deployment and Cost Considerations", page_break=False)')

# 4. Images: 4.2 inches width, compact caption spacing
text = text.replace('width=Inches(4.6)', 'width=Inches(4.2)')
text = text.replace('p_cap.paragraph_format.space_after = Pt(10)', 'p_cap.paragraph_format.space_after = Pt(5)')

# 5. Tables: compact padding, 8.0pt font
text = text.replace('r.font.size = Pt(8.5)', 'r.font.size = Pt(8.0)')
text = text.replace('r.font.size = Pt(9.0)', 'r.font.size = Pt(8.5)')
text = text.replace('p_cell.paragraph_format.line_spacing = 1.15', 'p_cell.paragraph_format.line_spacing = 1.05')

# 6. Code boxes: 8.0pt font
text = text.replace('r.font.size = Pt(9.0)\n        r.font.color.rgb = RGBColor(226, 232, 240)', 'r.font.size = Pt(8.0)\n        r.font.color.rgb = RGBColor(226, 232, 240)')

# 7. Update Table of Contents page numbers in text to match new target 28-page pagination
old_toc = '''    toc_items = [
        ("Certificate of Approval", "iii"),
        ("Declaration of Original Work", "iv"),
        ("Acknowledgements", "v"),
        ("Abstract", "vi"),
        ("List of Figures", "viii"),
        ("List of Tables", "ix"),
        ("1. Introduction", "1"),
        ("   1.1 Background and Context", "1"),
        ("   1.2 Problem Statement", "2"),
        ("   1.3 Project Objectives", "3"),
        ("   1.4 Scope and Boundaries", "4"),
        ("   1.5 Motivation and Expected Benefits", "5"),
        ("2. Existing System and Proposed Solution", "6"),
        ("   2.1 Existing Approaches to Cloud Cost Monitoring", "6"),
        ("   2.2 Limitations of the Existing Approaches", "7"),
        ("   2.3 Proposed Cloud Waste Hunter Solution", "8"),
        ("   2.4 Key Features Verified in the Implementation", "9"),
        ("   2.5 Functional Requirements", "10"),
        ("   2.6 Non-Functional Requirements", "11"),
        ("   2.7 Assumptions and Constraints", "12"),
        ("3. Technology Stack and System Requirements", "13"),
        ("   3.1 Programming Languages and Frameworks", "13"),
        ("   3.2 Frontend Technologies", "13"),
        ("   3.3 Backend Technologies and API Framework", "14"),
        ("   3.4 AWS Services and SDKs", "14"),
        ("   3.5 Gemini AI Integration", "15"),
        ("   3.6 Terraform and GitOps Tools", "15"),
        ("   3.7 Testing Frameworks and Dependencies", "16"),
        ("   3.8 Operating System and Runtime Requirements", "16"),
        ("   3.9 Installation Prerequisites", "17"),
        ("4. System Architecture and Design", "18"),
        ("   4.1 High-Level System Architecture", "18"),
        ("   4.2 Component Responsibilities", "19"),
        ("   4.3 Frontend-Backend Interaction", "20"),
        ("   4.4 Data Flow and Module Interactions", "21"),
        ("   4.5 End-to-End Workflow", "22"),
        ("   4.6 Security and Approval Workflow", "23"),
        ("   4.7 Proposed Deployment Architecture", "24"),
        ("5. Module Implementation", "25"),
        ("   5.1 Overview of the Seven Modules", "25"),
        ("   5.2 Module 1: Resource Discovery and Telemetry Ingestion", "26"),
        ("   5.3 Module 2: Cloud Waste Detection Rules Engine", "27"),
        ("   5.4 Module 3: Cost and Carbon Footprint Estimation", "28"),
        ("   5.5 Module 4: Google Gemini AI Advisor Synthesis", "29"),
        ("   5.6 Module 5: Terraform HCL Remediation Patch Generation", "30"),
        ("   5.7 Module 6: Terraform CLI Safety Gates and Plan Integrity Verification", "31"),
        ("   5.8 Module 7: GitOps Pull Request Review and Approval Workflow", "32"),
        ("   5.9 Inter-Module Communication", "33"),
        ("   5.10 Error Handling and Failure Scenarios", "34"),
        ("   5.11 Implementation Limitations", "34"),
        ("6. Security and Safety Controls", "35"),
        ("   6.1 AWS Credential Management", "35"),
        ("   6.2 IAM Roles and Least-Privilege Permissions", "35"),
        ("   6.3 AWS Identity Verification", "36"),
        ("   6.4 Gemini API Key Protection", "36"),
        ("   6.5 Live Mode versus Demo Mode", "37"),
        ("   6.6 Terraform Plan Validation and Integrity Verification", "37"),
        ("   6.7 Human Approval and Destructive-Action Safeguards", "38"),
        ("   6.8 Plan Expiry and Audit Logging", "38"),
        ("   6.9 GitOps Review and Approval Boundaries", "39"),
        ("   6.10 Security Limitations and Recommendations", "39"),
        ("7. Installation, Configuration and Operation", "40"),
        ("   7.1 Prerequisites", "40"),
        ("   7.2 Obtaining the Source Code", "40"),
        ("   7.3 Python Environment Setup", "40"),
        ("   7.4 Dependency Installation", "41"),
        ("   7.5 External Tool Installation", "41"),
        ("   7.6 Environment Configuration", "41"),
        ("   7.7 AWS Configuration", "42"),
        ("   7.8 Gemini Configuration", "42"),
        ("   7.9 Starting the Application", "42"),
        ("   7.10 Accessing the Application Interface", "43"),
        ("   7.11 Running Automated Tests", "43"),
        ("   7.12 Troubleshooting", "43"),
        ("8. Testing, Results and Discussion", "44"),
        ("   8.1 Testing Environment", "44"),
        ("   8.2 Testing Methodology", "44"),
        ("   8.3 Unit and Integration Testing", "45"),
        ("   8.4 Functional Test Cases", "45"),
        ("   8.5 AWS Integration Verification", "48"),
        ("   8.6 Gemini Integration Verification", "48"),
        ("   8.7 Terraform Safety Verification", "49"),
        ("   8.8 GitOps Workflow Verification", "49"),
        ("   8.9 Observed Test Results", "50"),
        ("   8.10 Discussion and Limitations", "52"),
        ("9. Proposed AWS EC2 Deployment and Cost Considerations", "53"),
        ("   9.1 Deployment Objectives", "53"),
        ("   9.2 Existing Application Compatibility", "53"),
        ("   9.3 Proposed EC2 Architecture", "54"),
        ("   9.4 Operating System and Instance Selection", "54"),
        ("   9.5 IAM Instance Role Configuration", "55"),
        ("   9.6 Network Access and Application Security", "55"),
        ("   9.7 Application Process Management", "56"),
        ("   9.8 Logging and Operational Monitoring", "56"),
        ("   9.9 Free Tier Eligibility and Cost Considerations", "57"),
        ("   9.10 Deployment Status and Remaining Work", "58"),
        ("10. Limitations and Future Enhancements", "59"),
        ("   10.1 Current Technical Limitations", "59"),
        ("   10.2 Integration and Deployment Limitations", "59"),
        ("   10.3 Potential Improvements", "60"),
        ("   10.4 Future Development Opportunities", "60"),
        ("11. Conclusion", "61"),
        ("   11.1 Summary of the Project", "61"),
        ("   11.2 Achievement of Objectives", "61"),
        ("   11.3 Verified Outcomes", "62"),
        ("   11.4 Final Assessment", "62"),
        ("12. References", "63"),
        ("13. Appendices", "65"),
        ("   13.1 Selected Configuration Templates", "65"),
        ("   13.2 Additional Test Evidence", "66"),
        ("   13.3 Relevant API Details", "67"),
        ("   13.4 Additional Technical Diagrams", "68")
    ]'''

new_toc = '''    toc_items = [
        ("Certificate of Approval & Declaration", "ii"),
        ("Acknowledgements & Abstract", "iii"),
        ("Table of Contents & Lists", "iv"),
        ("1. Introduction", "1"),
        ("   1.1 Background and Context", "1"),
        ("   1.2 Problem Statement", "1"),
        ("   1.3 Project Objectives", "2"),
        ("   1.4 Scope and Boundaries", "2"),
        ("   1.5 Motivation and Expected Benefits", "3"),
        ("2. Existing System and Proposed Solution", "3"),
        ("   2.1 Existing Approaches to Cloud Cost Monitoring", "3"),
        ("   2.2 Limitations of the Existing Approaches", "4"),
        ("   2.3 Proposed Cloud Waste Hunter Solution", "4"),
        ("   2.4 Key Features Verified in the Implementation", "5"),
        ("   2.5 Functional Requirements", "5"),
        ("   2.6 Non-Functional Requirements", "6"),
        ("   2.7 Assumptions and Constraints", "6"),
        ("3. Technology Stack and System Requirements", "7"),
        ("   3.1 Programming Languages and Frameworks", "7"),
        ("   3.2 Frontend Technologies", "7"),
        ("   3.3 Backend Technologies and API Framework", "7"),
        ("   3.4 AWS Services and SDKs", "8"),
        ("   3.5 Gemini AI Integration", "8"),
        ("   3.6 Terraform and GitOps Tools", "8"),
        ("   3.7 Testing Frameworks and Dependencies", "9"),
        ("   3.8 Operating System and Runtime Requirements", "9"),
        ("   3.9 Installation Prerequisites", "9"),
        ("4. System Architecture and Design", "10"),
        ("   4.1 High-Level System Architecture", "10"),
        ("   4.2 Component Responsibilities", "11"),
        ("   4.3 Frontend-Backend Interaction", "11"),
        ("   4.4 Data Flow and Module Interactions", "11"),
        ("   4.5 End-to-End Workflow", "12"),
        ("   4.6 Security and Approval Workflow", "13"),
        ("   4.7 Proposed Deployment Architecture", "14"),
        ("5. Module Implementation", "15"),
        ("   5.1 Overview of the Seven Modules", "15"),
        ("   5.2 Module 1: Resource Discovery and Telemetry Ingestion", "15"),
        ("   5.3 Module 2: Cloud Waste Detection Rules Engine", "16"),
        ("   5.4 Module 3: Cost and Carbon Footprint Estimation", "16"),
        ("   5.5 Module 4: Google Gemini AI Advisor Synthesis", "17"),
        ("   5.6 Module 5: Terraform HCL Remediation Patch Generation", "17"),
        ("   5.7 Module 6: Terraform CLI Safety Gates and Plan Integrity Verification", "18"),
        ("   5.8 Module 7: GitOps Pull Request Review and Approval Workflow", "18"),
        ("   5.9 Inter-Module Communication", "19"),
        ("   5.10 Error Handling and Failure Scenarios", "19"),
        ("   5.11 Implementation Limitations", "19"),
        ("6. Security and Safety Controls", "20"),
        ("   6.1 AWS Credential Management", "20"),
        ("   6.2 IAM Roles and Least-Privilege Permissions", "20"),
        ("   6.3 AWS Identity Verification", "20"),
        ("   6.4 Gemini API Key Protection", "20"),
        ("   6.5 Live Mode versus Demo Mode", "21"),
        ("   6.6 Terraform Plan Validation and Integrity Verification", "21"),
        ("   6.7 Human Approval and Destructive-Action Safeguards", "21"),
        ("   6.8 Plan Expiry and Audit Logging", "21"),
        ("   6.9 GitOps Review and Approval Boundaries", "22"),
        ("   6.10 Security Limitations and Recommendations", "22"),
        ("7. Installation, Configuration and Operation", "22"),
        ("   7.1 Prerequisites", "22"),
        ("   7.2 Obtaining the Source Code", "22"),
        ("   7.3 Python Environment Setup", "22"),
        ("   7.4 Dependency Installation", "23"),
        ("   7.5 External Tool Installation", "23"),
        ("   7.6 Environment Configuration", "23"),
        ("   7.7 AWS Configuration", "23"),
        ("   7.8 Gemini Configuration", "23"),
        ("   7.9 Starting the Application", "23"),
        ("   7.10 Accessing the Application Interface", "24"),
        ("   7.11 Running Automated Tests", "24"),
        ("   7.12 Troubleshooting", "24"),
        ("8. Testing, Results and Discussion", "24"),
        ("   8.1 Testing Environment", "24"),
        ("   8.2 Testing Methodology", "24"),
        ("   8.3 Unit and Integration Testing", "25"),
        ("   8.4 Functional Test Cases", "25"),
        ("   8.5 AWS Integration Verification", "25"),
        ("   8.6 Gemini Integration Verification", "25"),
        ("   8.7 Terraform Safety Verification", "25"),
        ("   8.8 GitOps Workflow Verification", "25"),
        ("   8.9 Observed Test Results", "25"),
        ("   8.10 Discussion and Limitations", "26"),
        ("9. Proposed AWS EC2 Deployment and Cost Considerations", "26"),
        ("   9.1 Deployment Objectives", "26"),
        ("   9.2 Existing Application Compatibility", "26"),
        ("   9.3 Proposed EC2 Architecture", "26"),
        ("   9.4 Operating System and Instance Selection", "27"),
        ("   9.5 IAM Instance Role Configuration", "27"),
        ("   9.6 Network Access and Application Security", "27"),
        ("   9.7 Application Process Management", "27"),
        ("   9.8 Logging and Operational Monitoring", "27"),
        ("   9.9 Free Tier Eligibility and Cost Considerations", "28"),
        ("   9.10 Deployment Status and Remaining Work", "28"),
        ("10. Limitations and Future Enhancements", "28"),
        ("   10.1 Current Technical Limitations", "28"),
        ("   10.2 Integration and Deployment Limitations", "28"),
        ("   10.3 Potential Improvements", "28"),
        ("   10.4 Future Development Opportunities", "28"),
        ("11. Conclusion", "29"),
        ("   11.1 Summary of the Project", "29"),
        ("   11.2 Achievement of Objectives", "29"),
        ("   11.3 Verified Outcomes", "29"),
        ("   11.4 Final Assessment", "29"),
        ("12. References", "30"),
        ("13. Appendices", "30"),
        ("   13.1 Selected Configuration Templates", "30"),
        ("   13.2 Additional Test Evidence", "30"),
        ("   13.3 Relevant API Details", "30"),
        ("   13.4 Additional Technical Diagrams", "30")
    ]'''

if old_toc in text:
    text = text.replace(old_toc, new_toc)

with open('generate_full_project_report.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Updated calibration to target 27-29 pages successfully.')
