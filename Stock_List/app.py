from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
import os  # For handling file paths
import pandas as pd  # For reading and processing Excel files
import logging  # For logging

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Hardcoded credentials for login
USERNAME = "Admin"
PASSWORD = "adminrs123"

# Define the path to the Excel file
EXCEL_FILE_PATH = os.path.join("files", "stockList.xlsx")


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':  # Handle form submission
        username = request.form['username']
        password = request.form['password']

        # Check if the credentials match
        if username == USERNAME and password == PASSWORD:
            session['user'] = username  # Save username in session
            return redirect(url_for('dashboard'))  # Redirect to dashboard
        else:
            return render_template('login.html', error="Invalid credentials!")  # Show error

    # Render the login page for GET requests
    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'user' in session:  # Check if the user is logged in
        return render_template('stockDashboard.html')  # Show the dashboard
    else:
        return redirect(url_for('login'))  # Redirect to login if not logged in


@app.route('/view-sheet1')
def view_sheet1():
    if os.path.exists(EXCEL_FILE_PATH):
        try:
            df = pd.read_excel(EXCEL_FILE_PATH, sheet_name='Sheet1')
            df['Category'] = df['Category'].str.strip()  # Remove leading/trailing spaces
            grouped_data = df.groupby('Category').size().reset_index(name='Count')
            grouped_data['Link'] = grouped_data['Category'].apply(
                lambda x: f'<a href="{url_for("category_items", category_name=x)}">{x}</a>'
            )
            data_html = grouped_data.to_html(classes='table table-striped', index=False, escape=False)
            return render_template('view_sheet1.html', table_data=data_html, filename="stockList.xlsx")
        except Exception as e:
            return f"Error reading the Excel file: {e}"
    else:
        return "The Excel file was not found."


@app.route('/view-remark-list')
def view_remark_list():
    if os.path.exists(EXCEL_FILE_PATH):
        try:
            df = pd.read_excel(EXCEL_FILE_PATH, sheet_name='Remark List')  # Access the Remark List sheet
            df['Remark'] = df['Remark'].str.strip()  # Clean up the data
            
            # Handle non-finite values in Qty
            df['Qty'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(0).astype(int)

            # Format the Date
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.strftime('%d-%m-%Y')

            # Capture the search query
            search_query = request.args.get('search', '').strip().lower()
            if search_query:
                df = df[df['Product name'].str.lower().str.contains(search_query, na=False)]

            # Pagination logic
            page = request.args.get('page', 1, type=int)
            per_page = 10
            total = len(df)
            start = (page - 1) * per_page
            end = start + per_page
            items = df.iloc[start:end]
            total_pages = (total + per_page - 1) // per_page

            # Generate pagination links
            next_page = page + 1 if page < total_pages else None
            prev_page = page - 1 if page > 1 else None

            data_html = items.to_html(classes='table table-striped', index=False, na_rep='')
            return render_template(
                'view_remark_list.html',
                table_data=data_html,
                page=page,
                total_pages=total_pages,
                next_page=next_page,
                prev_page=prev_page,
                search_query=search_query
            )
        except Exception as e:
            return f"Error reading the Excel file: {e}"
    else:
        return "The Excel file was not found."


@app.route('/category/<category_name>')
def category_items(category_name):
    search_query = request.args.get('search', '').strip().lower()  # Get the search query
    if os.path.exists(EXCEL_FILE_PATH):  # Check if the Excel file exists
        try:
            df = pd.read_excel(EXCEL_FILE_PATH, sheet_name='Sheet1')
            df['Category'] = df['Category'].str.strip()  # Remove leading/trailing spaces

            # Explicitly create a copy of the filtered DataFrame
            category_data = df[df['Category'].str.lower() == category_name.lower()].copy()

            if category_data.empty:
                return f"No data found for category: {category_name}"

            # Filter by search query if provided
            if search_query:
                category_data = category_data[
                    category_data['Item Name'].str.lower().str.contains(search_query, na=False)
                ]

            category_data['Date'] = pd.to_datetime(category_data['Date'], errors='coerce').dt.strftime('%d-%m-%Y')
            category_data = category_data[['Category', 'Sub Category', 'Item Name', 'Unit', 'Qty', 'Date']]

            # Pagination logic
            page = request.args.get('page', 1, type=int)
            per_page = 10
            total = len(category_data)
            start = (page - 1) * per_page
            end = start + per_page
            items = category_data.iloc[start:end]
            total_pages = (total + per_page - 1) // per_page

            # Generate pagination links
            next_page = page + 1 if page < total_pages else None
            prev_page = page - 1 if page > 1 else None

            data_html = items.to_html(classes='table table-striped', index=False, na_rep='')
            return render_template(
                'category_items.html',
                table_data=data_html,
                category=category_name,
                page=page,
                total_pages=total_pages,
                next_page=next_page,
                prev_page=prev_page,
                search_query=search_query
            )
        except Exception as e:
            return f"Error reading the Excel file: {e}"
    else:
        return "The Excel file was not found."


@app.route('/download-sheet1')
def download_sheet1():
    return send_from_directory("files", "stockList.xlsx", as_attachment=True)


@app.route('/enter-out-stock')
def enter_out_stock():
    return render_template('enter_out_stock.html')


@app.route('/submit_stock', methods=['POST'])
def submit_stock():
    try:
        product_name = request.form['product_name']
        if isinstance(product_name, str):
            product_name = product_name.strip()  # Only strip if it's a string
        quantity = int(request.form['quantity'])
        date = request.form['date']

        logging.debug(f"Received request to update stock for product: {product_name}, quantity: {quantity}, date: {date}")

        # Load Excel file
        xl = pd.ExcelFile(EXCEL_FILE_PATH)
        sheet1 = xl.parse('Sheet1')
        remark_list = xl.parse('Remark List')  # Access the Remark List sheet

        updated = False

        # Check for product in Sheet1
        if 'Item Name' in sheet1.columns:
            logging.debug(f"Checking Sheet1 for product: {product_name}")
            for index, row in sheet1.iterrows():
                item_name = row['Item Name']
                if isinstance(item_name, str) and item_name.strip().lower() == product_name.lower():
                    logging.debug(f"Found product in Sheet1: {row['Item Name']} with current quantity: {row['Qty']}")
                    if row['Qty'] >= quantity:  # Ensure enough stock
                        sheet1.at[index, 'Qty'] -= quantity
                        sheet1.at[index, 'Last Updated'] = date
                        updated = True
                        logging.debug(f"Updated product in Sheet1: {row['Item Name']} to new quantity: {sheet1.at[index, 'Qty']}")
                    else:
                        flash(f"Not enough stock for '{product_name}'!", 'error')
                        return redirect(url_for('enter_out_stock'))
        else:
            logging.error("Column 'Item Name' not found in Sheet1")

        # Check for product in Remark List
        if not updated and 'Product name' in remark_list.columns:
            logging.debug(f"Checking Remark List for product: {product_name}")
            for index, row in remark_list.iterrows():
                product_name_remark = row['Product name']
                if isinstance(product_name_remark, str) and product_name_remark.strip().lower() == product_name.lower():
                    logging.debug(f"Found product in Remark List: {row['Product name']} with current quantity: {row['Qty']}")
                    if row['Qty'] >= quantity:  # Ensure enough stock
                        remark_list.at[index, 'Qty'] -= quantity
                        remark_list.at[index, 'Last Updated'] = date
                        updated = True
                        logging.debug(f"Updated product in Remark List: {row['Product name']} to new quantity: {remark_list.at[index, 'Qty']}")
                    else:
                        flash(f"Not enough stock for '{product_name}'!", 'error')
                        return redirect(url_for('enter_out_stock'))
        else:
            logging.error("Column 'Product name' not found in Remark List")

        if updated:
            # Save the Excel file
            with pd.ExcelWriter(EXCEL_FILE_PATH, engine='openpyxl') as writer:
                sheet1.to_excel(writer, sheet_name='Sheet1', index=False)
                remark_list.to_excel(writer, sheet_name='Remark List', index=False)  # Save to Remark List

            flash(f"Stock for '{product_name}' successfully updated!", 'success')
            logging.debug(f"Stock for '{product_name}' successfully updated in Excel file.")
        else:
            flash(f"Product '{product_name}' not found!", 'error')
            logging.debug(f"Product '{product_name}' not found in any sheet.")

    except Exception as e:
        flash(f"An error occurred: {str(e)}", 'error')
        logging.error(f"An error occurred while updating stock: {str(e)}")

    return redirect(url_for('enter_out_stock'))  # Redirect back to the form


@app.route('/update-stock', methods=['GET', 'POST'])
def update_stock():
    if request.method == 'GET':
        # Populate dropdowns for Category and Sub Category (for Sheet1 only)
        if os.path.exists(EXCEL_FILE_PATH):
            try:
                df_sheet1 = pd.read_excel(EXCEL_FILE_PATH, sheet_name='Sheet1')
                categories = sorted(df_sheet1['Category'].dropna().unique().tolist())
                sub_categories = sorted(df_sheet1['Sub Category'].dropna().unique().tolist())
                return render_template('update_stock.html', categories=categories, sub_categories=sub_categories)
            except Exception as e:
                return f"Error reading the Excel file: {e}"
        else:
            return "The Excel file was not found."

    elif request.method == 'POST':
        try:
            # Gather form data
            sheet = request.form['sheet']
            category = request.form['category']
            sub_category = request.form['sub_category']
            product_name = request.form['product_name'].strip()
            quantity = int(request.form['quantity'])
            date = request.form['date']

            # Load Excel file
            xl = pd.ExcelFile(EXCEL_FILE_PATH)
            df = xl.parse(sheet)

            # Check if the product exists
            product_exists = product_name in df['Item Name'].values

            if product_exists:
                # Update existing product
                df.loc[df['Item Name'] == product_name, 'Qty'] += quantity
                df.loc[df['Item Name'] == product_name, 'Last Updated'] = date
            else:
                # Add new product
                new_row = {
                    'Category': category,
                    'Sub Category': sub_category,
                    'Item Name': product_name,
                    'Qty': quantity,
                    'Date': date
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

            # Save the updated Excel file
            with pd.ExcelWriter(EXCEL_FILE_PATH, engine='openpyxl') as writer:
                for sheet_name in xl.sheet_names:
                    if sheet_name == sheet:
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                    else:
                        xl.parse(sheet_name).to_excel(writer, sheet_name=sheet_name, index=False)

            flash(f"Stock for '{product_name}' successfully updated!", 'success')
        except Exception as e:
            flash(f"An error occurred: {str(e)}", 'error')

        return redirect(url_for('update_stock'))
        pass


@app.route('/logout')
def logout():
    session.pop('user', None)  # Clear the session
    return redirect(url_for('login'))  # Redirect to login page


if __name__ == '__main__':
    app.run(debug=True)
