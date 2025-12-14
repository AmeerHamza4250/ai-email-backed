"""
CSV parser utility for lead imports using pandas.
"""
import pandas as pd
import io
import sys
from typing import List, Dict, Tuple, Any
from src.utils.validators import validate_email_address
from src.utils.logger import get_logger

logger = get_logger(__name__)


def parse_csv_file(file_content: bytes) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Parse CSV/TSV/Excel file content and return valid rows with errors.
    """
    valid_rows = []
    errors = []
    df = None
    
    # Force print to stdout
    print("=" * 50, file=sys.stderr, flush=True)
    print("CSV PARSER CALLED", file=sys.stderr, flush=True)
    print(f"File size: {len(file_content)} bytes", file=sys.stderr, flush=True)
    
    # Show first 500 bytes of raw content for debugging
    try:
        raw_preview = file_content[:500].decode('utf-8', errors='replace')
        print(f"Raw content preview:\n{raw_preview}", file=sys.stderr, flush=True)
    except:
        print("Could not decode raw content", file=sys.stderr, flush=True)
    
    # Try different parsing methods
    parsing_methods = [
        ("comma", lambda: pd.read_csv(io.BytesIO(file_content), sep=',', encoding='utf-8-sig')),
        ("tab", lambda: pd.read_csv(io.BytesIO(file_content), sep='\t', encoding='utf-8-sig')),
        ("semicolon", lambda: pd.read_csv(io.BytesIO(file_content), sep=';', encoding='utf-8-sig')),
        ("auto", lambda: pd.read_csv(io.BytesIO(file_content), sep=None, engine='python', encoding='utf-8-sig')),
        ("excel", lambda: pd.read_excel(io.BytesIO(file_content))),
    ]
    
    for method_name, method_func in parsing_methods:
        try:
            df = method_func()
            if df is not None and len(df.columns) >= 2:
                print(f"SUCCESS with method: {method_name}", file=sys.stderr, flush=True)
                print(f"Columns found: {list(df.columns)}", file=sys.stderr, flush=True)
                break
            else:
                print(f"Method {method_name}: Only {len(df.columns) if df is not None else 0} columns", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"Method {method_name} failed: {e}", file=sys.stderr, flush=True)
            continue
    
    if df is None or df.empty:
        errors.append("Could not parse file. Please save as CSV (comma-separated).")
        return valid_rows, errors
    
    print(f"DataFrame shape: {df.shape}", file=sys.stderr, flush=True)
    print(f"Columns: {list(df.columns)}", file=sys.stderr, flush=True)
    print(f"First row: {df.iloc[0].to_dict() if len(df) > 0 else 'empty'}", file=sys.stderr, flush=True)
    
    # Normalize column names
    original_columns = list(df.columns)
    df.columns = [str(col).lower().strip() for col in df.columns]
    print(f"Normalized columns: {list(df.columns)}", file=sys.stderr, flush=True)
    
    # Find columns by various possible names
    name_col = None
    email_col = None
    company_col = None
    
    # Common column name variations
    name_variations = [
        'name', 'fullname', 'full name', 'full_name', 'contact', 'lead name', 'leadname',
        'recipient_name', 'recipient name', 'recipientname', 'to_name', 'to name',
        'contact_name', 'contact name', 'contactname', 'person_name', 'person name'
    ]
    
    email_variations = [
        'email', 'e-mail', 'mail', 'email address', 'emailaddress', 'email_address',
        'recipient_email', 'recipient email', 'recipientemail', 'to_email', 'to email',
        'contact_email', 'contact email', 'contactemail', 'e_mail', 'e mail'
    ]
    
    company_variations = [
        'company', 'company name', 'companyname', 'company_name', 'org', 'organization',
        'organisation', 'business', 'business name', 'businessname', 'business_name',
        'organization_name', 'organization name', 'org_name', 'org name'
    ]
    
    for col in df.columns:
        col_lower = col.lower().strip()
        if name_col is None and col_lower in name_variations:
            name_col = col
        if email_col is None and col_lower in email_variations:
            email_col = col
        if company_col is None and col_lower in company_variations:
            company_col = col
    
    print(f"Mapped: name={name_col}, email={email_col}, company={company_col}", file=sys.stderr, flush=True)
    
    if not name_col:
        errors.append(f"Missing required column: name. Found columns: {original_columns}")
        return valid_rows, errors
    
    if not email_col:
        errors.append(f"Missing required column: email. Found columns: {original_columns}")
        return valid_rows, errors
    
    # Process rows
    for idx, row in df.iterrows():
        row_num = idx + 2
        
        try:
            name_val = row.get(name_col)
            email_val = row.get(email_col)
            
            # Convert to string and clean
            name = str(name_val).strip() if pd.notna(name_val) else ''
            email = str(email_val).strip() if pd.notna(email_val) else ''
            
            # Skip nan strings
            if name.lower() == 'nan':
                name = ''
            if email.lower() == 'nan':
                email = ''
            
            # Skip empty rows
            if not name and not email:
                continue
            
            # Validate
            if not name:
                errors.append(f"Row {row_num}: Name is required")
                continue
            
            if not email:
                errors.append(f"Row {row_num}: Email is required")
                continue
            
            is_valid, email_error = validate_email_address(email)
            if not is_valid:
                errors.append(f"Row {row_num}: Invalid email - {email_error}")
                continue
            
            # Get company if available
            company = None
            if company_col:
                company_val = row.get(company_col)
                if pd.notna(company_val):
                    company = str(company_val).strip()
                    if company.lower() == 'nan':
                        company = None
            
            # Extract specific fields for dedicated columns
            email_id = None
            email_subject = None
            email_type = None
            sent_status = None
            reply_status = None
            time_to_reply_hours = None
            
            # Map common column names to our fields
            for col in df.columns:
                col_lower = col.lower().strip()
                col_val = row.get(col)
                
                if pd.notna(col_val):
                    val = col_val
                    # Convert to string for storage (except keep numeric for time_to_reply)
                    if col_lower in ['email_id', 'emailid']:
                        email_id = str(val).strip() if str(val).strip().lower() != 'nan' else None
                    elif col_lower in ['email_subject', 'emailsubject', 'subject']:
                        email_subject = str(val).strip() if str(val).strip().lower() != 'nan' else None
                    elif col_lower in ['email_type', 'emailtype', 'type']:
                        email_type = str(val).strip() if str(val).strip().lower() != 'nan' else None
                    elif col_lower in ['sent_status', 'sentstatus', 'sent']:
                        sent_status = str(val).strip() if str(val).strip().lower() != 'nan' else None
                    elif col_lower in ['reply_status', 'replystatus', 'replied']:
                        # Handle both boolean and string
                        if isinstance(val, bool):
                            reply_status = str(val)
                        else:
                            reply_status = str(val).strip() if str(val).strip().lower() != 'nan' else None
                    elif col_lower in ['time_to_reply_hours', 'timetoreplyhours', 'time_to_reply', 'reply_time']:
                        time_to_reply_hours = str(val).strip() if str(val).strip().lower() != 'nan' else None
            
            # Collect any remaining fields for additional_data
            additional_data = {}
            for col in df.columns:
                # Skip the columns we're already using
                if col in [name_col, email_col, company_col]:
                    continue
                
                # Skip columns we've mapped to dedicated fields
                col_lower = col.lower().strip()
                if col_lower in ['email_id', 'emailid', 'email_subject', 'emailsubject', 'subject',
                                'email_type', 'emailtype', 'type', 'sent_status', 'sentstatus', 'sent',
                                'reply_status', 'replystatus', 'replied', 'time_to_reply_hours',
                                'timetoreplyhours', 'time_to_reply', 'reply_time']:
                    continue
                
                col_val = row.get(col)
                if pd.notna(col_val):
                    # Convert to appropriate type
                    val = col_val
                    if isinstance(val, (int, float)):
                        # Keep numeric types
                        pass
                    elif isinstance(val, bool):
                        # Keep boolean types
                        pass
                    else:
                        # Convert to string and clean
                        val = str(val).strip()
                        if val.lower() == 'nan' or val == '':
                            continue
                    
                    # Store with original column name (normalized)
                    additional_data[col] = val
            
            # Only add additional_data if it has content
            final_additional_data = additional_data if additional_data else None
            
            valid_rows.append({
                'name': name,
                'email': email,
                'company': company,
                'email_id': email_id,
                'email_subject': email_subject,
                'email_type': email_type,
                'sent_status': sent_status,
                'reply_status': reply_status,
                'time_to_reply_hours': time_to_reply_hours,
                'additional_data': final_additional_data
            })
            
        except Exception as e:
            errors.append(f"Row {row_num}: Error - {str(e)}")
            continue
    
    print(f"Result: {len(valid_rows)} valid, {len(errors)} errors", file=sys.stderr, flush=True)
    print("=" * 50, file=sys.stderr, flush=True)
    
    return valid_rows, errors
