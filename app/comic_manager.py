import json
import msal
from flask import Flask, request, redirect, url_for, session, render_template
import requests
from tool_suite import CoverDateCorrector
import pandas as pd
import app_config


class ComicBookManagerApp:
    
    def __init__(self, app):
        self.app = app
        self.cdc = CoverDateCorrector()

    def register_routes(self):
        self.app.add_url_rule("/", "index", self.index)
        self.app.add_url_rule("/tools", "tools", self.tools)
        self.app.add_url_rule("/tools/cover_date_corrector", "cover_date_corrector", self.cover_date_corrector, methods=['GET', 'POST'])
        self.app.add_url_rule("/tools/cover_date_corrector/finalize", "cover_date_corrector_finalize", self.cover_date_corrector_finalize, methods=['GET', 'POST', 'PATCH'])
    
    def index(self):
        if not self.check_for_user():
            return redirect(url_for("login"))
        return render_template('index.html', user=session["user"])
    
    def tools(self):
        if not self.check_for_user():
            return redirect(url_for("login"))
        return render_template('tool_menu.html')
    
    def cover_date_corrector(self):
        MAW_data = pd.DataFrame()
        has_approved_data=False
        drive_data = pd.DataFrame()

        if not self.check_for_user():
            return redirect(url_for("login"))
        
        if request.method == "POST":
            sid = request.form.get("sid")
            filter_term = request.form.get("filter_term")
            search_term = request.form.get("search_criteria")
            
            if sid:
                self.cdc.set_SID(sid)
                MAW_data = self.cdc.load_initial_MAW_data()
            
            elif filter_term:
                MAW_data=self.cdc.add_filter_to_MAW_data(filter_term)
            
            elif "fetch_button" in request.form:
                MAW_data=self.cdc.maw_data.fetch_MAW_data()
            
            elif "approve_button" in request.form:
                has_approved_data=True
                MAW_data = self.cdc.maw_data.get_active_MAW_data()
            
            elif search_term:
                has_approved_data=True
                drive_data = self.cdc_fetch_graph_data(search_term)
                self.cdc.drive_data.set_folder_data(self.create_comic_folder_structure(self.cdc_get_monthly_packages_folder_id()))
            
            elif "remove_entry" in request.form:
                has_approved_data=True
                file_name = request.form.get("remove_entry")
                if file_name:
                    drive_data = self.cdc.drive_data.remove_entry_from_drive_data(file_name)
                    print(drive_data)
            
            elif "remove_all_after" in request.form:
                has_approved_data=True
                index = request.form.get("remove_all_after")
                if index:
                    index = int(index)
                    drive_data = self.cdc.drive_data.remove_all_entries_after(index)
            
            elif "approve_drive_button" in request.form:
                return redirect(url_for("cover_date_corrector_finalize"))

        return render_template('cover_date_corrector.html', data=MAW_data, approved_data=has_approved_data, drive_data=drive_data)

    def cover_date_corrector_finalize(self):
        preview_data = self.cdc.create_preview_data()

        if request.method == 'POST':
            publisher = request.form.get("publisher")
            final_data = self.cdc.create_final_data(publisher)
            for index, row in final_data.iterrows():
                print(row)
                url = f"https://graph.microsoft.com/v1.0/me/drive/items/{row['File ID']}"
                payload = {
                    "parentReference":{
                        "id": f"{row['Destination ID']}"
                    }
                }
                headers = {
                    "Authorization": "Bearer " + session.get("access_token"),
                    "Content-Type": "application/json"
                }

                try:
                    response = requests.patch(url, data=json.dumps(payload), headers=headers)
                    response.raise_for_status()  # Raise an exception if the response status code is not 2xx
                    print("File Moved")
                except requests.exceptions.RequestException as e:
                    print(f"PATCH request failed: {e}")
                    return "OPERATION FAILED"
            return redirect(url_for("index"))

        return render_template('cover_date_corrector_preview.html', data=preview_data)

    def check_for_user(self):
        if session.get("user") and session.get("access_token"):
            return True
        return False
    
    def cdc_fetch_graph_data(self, search_term):
        url = "https://graph.microsoft.com/v1.0/me/drive/root/search(q='%s')?select=name,parentReference,id" % (search_term)
        result = []
        
        while True:
            graph_data = requests.get(url, headers={'Authorization': 'Bearer ' + session.get("access_token")})
            
            if graph_data.status_code == 200:
                data = graph_data.json()
                result.extend(data['value'])
                next_link = data.get("@odata.nextLink")

                print(next_link)
                if next_link:
                    url = next_link
                else:
                    break
            else:
                print(graph_data)
                break
        return self.cdc.drive_data.parse_graph_response_to_data_frame(result)
    
    def cdc_get_monthly_packages_folder_id(self):
        url = "https://graph.microsoft.com/v1.0/me/drive/root/search(q='Monthly%20Packages')"
        graph_data = requests.get(url, headers={'Authorization': 'Bearer ' + session.get("access_token")})

        if graph_data.status_code == 200:
            data = graph_data.json()
            return self.cdc.drive_data.parse_graph_response_to_monthly_package_folder_id(data['value'])
        else:
            print("Error getting folder ID")
        
    def create_comic_folder_structure(self, root_folder_id):
        # Initialize the root folder structure
        root = {
            'folder_id': root_folder_id,
            'subfolders': {}
        }
        
        # Use the Microsoft Graph API to list the contents of the root folder
        folder_contents = self.get_folder_contents(root_folder_id)
        
        # Recursively process each item in the root folder
        for item in folder_contents:
            if "folder" in item:
                # If the item is a folder, create a subfolder structure
                folder_id = item['id']
                folder_name = item['name']
                root['subfolders'][folder_name] = self.create_publisher_structure(folder_id)

        return self.cdc.drive_data.set_folder_data(root)

    def create_publisher_structure(self, publisher_folder_id):
        # Initialize the publisher folder structure
        publisher = {
            'folder_id': publisher_folder_id,
            'subfolders': {}
        }

        # Retrieve the contents of the publisher folder
        publisher_contents = self.get_folder_contents(publisher_folder_id)

        # Process each item in the publisher folder
        for item in publisher_contents:
            if "folder" in item:
                # If the item is a folder, create a year structure
                folder_id = item['id']
                folder_name = item['name']
                year = folder_name
                publisher['subfolders'][year] = self.create_year_structure(folder_id)

        return publisher

    def create_year_structure(self, year_folder_id):
        # Initialize the year folder structure
        year = {
            'folder_id': year_folder_id,
            'subfolders': {}
        }

        # Retrieve the contents of the year folder
        year_contents = self.get_folder_contents(year_folder_id)

        # Process each item in the year folder (e.g., months)
        for item in year_contents:
            if "folder" in item:
                # If the item is a folder, create a month structure
                folder_id = item['id']
                folder_name = item['name']
                month = folder_name
                year['subfolders'][month] = {
                    'folder_id': folder_id
                }

        return year
    
    def get_folder_contents(self, folder_id):
        api_endpoint = f'https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}/children'

        try:
            response = requests.get(api_endpoint, headers={'Authorization': 'Bearer ' + session.get("access_token")})
            if response.status_code == 200:
                folder_contents = response.json()['value']
                return folder_contents
            else:
                raise Exception(f'Error fetching folder contents. Status code: {response.status_code}\n{response}')
        except Exception as e:
            # Handle exceptions and errors
            print(f'Error: {str(e)}')
            return None