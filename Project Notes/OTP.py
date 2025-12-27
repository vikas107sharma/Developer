"""
SALES OFFICER AUTHENTICATION FLOW NOTES
=======================================

1. API: /validate-mobile
    i. If user doesn't exist return
    ii. If password doesn't exist send OTP
        {otp: send on SMS, otp_encrypted: store in db, otp_expiry, store in db}
        response {pin: False, otp: true}
    iii. If password exists 
        response {pin: True, otp: False}


2. API: /validate-otp
    i. Check otp exists and not expired
    ii. Encrypt users OTP and verify with DB 
    iii. Update DB, otp=None, otp_expires_at=None, sales_officer_otp_validation=True


3. API: /set-pin
    i. Check if sales_officer_otp_validation is True in DB
    ii. Input (PIN) ----> [SHA-512 Hash] ----> [Add Secret Salt] ----> [Final SHA-512 Hash]
                                                                        |
                                                                        v
                                                            Stored in DB (Permanent)
                                                   (No way to go back to original PIN)
    
4. API: /login
        i. VERIFICATION SEQUENCE (LOGIN)
            =============================
            1. User enters '1234'.
            2. System hashes '1234' + Salt using the exact same logic.
            3. System compares the NEW hash with the STORED hash.
            4. If they match, the PIN is correct!
        
        ii. generate_access_token: 
                token = jwt.encode(
                    payload,  --> {user_id, ..., iat: , exp: }
                    config.auth.JWT_SECRET,
                    algorithm="HS256"
                )
        

5. API: /reset-pin
   Used for 'Forgot PIN' scenarios. It initiates the OTP flow for existing 
   users, allowing them to verify their identity via SMS before 
   overwriting their old PIN.

6. API: /resend-otp
   A helper endpoint that checks if a previously sent OTP has expired. 
   If expired, it generates and sends a new one; otherwise, it prevents 
   redundant SMS costs.


AUTHENTICATION SEQUENCE
=======================

Scenario A: First-time User (Registration)
------------------------------------------
Mobile App -> /validate-mobile -> Returns {otp: True, pin: False}
Mobile App -> /validate-otp    -> Verifies SMS code
Mobile App -> /set-pin         -> Sets the new login PIN
Mobile App -> /login           -> Receives JWT Access Token

Scenario B: Returning User (Login)
----------------------------------
Mobile App -> /validate-mobile -> Returns {otp: False, pin: True}
Mobile App -> /login           -> Authenticates with PIN and receives Token

Scenario C: Forgot PIN (Reset)
------------------------------
Mobile App -> /reset-pin       -> Triggers OTP SMS
Mobile App -> /validate-otp    -> Verifies SMS code
Mobile App -> /set-pin         -> Updates to a new PIN
Mobile App -> /login           -> Standard Login
"""

def auth_summary():
    # This file is structured for documentation purposes
    print("Documentation for Sales Officer Auth Flow loaded.")

if __name__ == "__main__":
    auth_summary()