import bcrypt

# Stored hash from database
stored_hash = b"$2a$10$j4OFblZHIgZPOypiTVgCPO0OFKkXtDWEigyQuW7yI4m2AAWcQGlBm"

# User input password to verify
password_attempt = ["passwordcompreface", "user"]
for i in password_attempt:
    # Verify the password
    if bcrypt.checkpw(i.encode(), stored_hash):
        print(f"{i} Password is correct!")
    else:
        print(f"{i} Password is incorrect!")
