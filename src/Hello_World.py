from Neon_Accessibility_Helper_Functions import *

conn = get_connection()
print("Hello World!")

# File Names (use these names when calling functions!)
# cleaned_test_20_percent.csv - Uploaded to Neon
# cleaned_train_80_percent.csv - Uploaded to Neon

row = get_row_by_index("cleaned_train_80_percent", 0, conn) # calling the example function
close_connection(conn) # close connection once done retrieving data
print(row)