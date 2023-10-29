import json
import os
from datetime import date
import pandas as pd
from MAW_Fetch import MAWFetcher

#Single Purpose: To organize comics based on their cover date
class CoverDateCorrector():

    def __init__(self):
        self.seriesid = None
        self.final_filtered_data = None
        self.final_drive_data = None
        self.maw_data = MAWDataManager()
        self.drive_data = DriveDataManager()

    def set_SID(self, sid):
        self.seriesid = sid
        self.maw_data.set_series_id(sid)

    def load_initial_MAW_data(self):
        self.maw_data.load_MAW_data()
        self.maw_data.filter_active_data()
        return self.maw_data.get_active_MAW_data()
    
    def add_filter_to_MAW_data(self, filter_term):
        self.maw_data.data_filter.add_filter(filter_term)
        self.maw_data.filter_active_data()
        return self.maw_data.get_active_MAW_data()
    
    def create_preview_data(self):
        destinations = self.extract_destination_folders()
        file_names = self.drive_data.active_data['File Name'].tolist()
        print(self.maw_data.active_data)
        issue_names = self.maw_data.active_data['Issue Name'].tolist()
        cover_dates = self.maw_data.active_data['Cover Date'].tolist()
        preview_list = pd.DataFrame(
            {
                "File Name": file_names,
                "Issue Name": issue_names,
                "Cover Date": cover_dates,
                "Destination Folder": destinations
            }
        )
        return preview_list
    
    def create_final_data(self, publisher):
        file_ids = self.drive_data.active_data['File ID'].tolist()
        months = self.maw_data.active_data["Month"].tolist()
        years = self.maw_data.active_data["Year"].tolist()
        destination_folder_ids = []

        for i in range(len(file_ids)):
            year = years[i]
            month = self.format_month(months[i])

            # Initialize the destination to the root of the folder_dict
            destination = self.drive_data.folder_dict

            # Check if the 'publisher' exists in the structure
            if publisher in destination['subfolders']:
                destination = destination['subfolders'][publisher]

                # Check if the 'year' exists in the publisher's subfolders
                if year in destination['subfolders']:
                    destination = destination['subfolders'][year]

                    # Check if the 'month' exists in the year's subfolders
                    if month in destination['subfolders']:
                        destination = destination['subfolders'][month]

                        # Get the final folder ID
                        folder_id = destination['folder_id']
                        destination_folder_ids.append(folder_id)
                    else:
                        # Handle the case when 'month' doesn't exist
                        print(f"Month {month} not found in the folder structure.")
                else:
                    # Handle the case when 'year' doesn't exist
                    print(f"Year {year} not found in the folder structure.")
            else:
                # Handle the case when 'publisher' doesn't exist
                print(f"Publisher {publisher} not found in the folder structure.")
        final_data = pd.DataFrame({
            'File ID': file_ids,
            'Destination ID': destination_folder_ids
        })
        return final_data
    
    def extract_destination_folders(self):
        destination_folders = []
        self.maw_data.split_active_data_dates()

        for index, row in self.maw_data.active_data.iterrows():
            month = self.format_month(row["Month"])
            year = row["Year"]

            destination_folder = f"root/Comics/Monthly Packages/[Publisher]/{year}/{month}"
            
            destination_folders.append(destination_folder)
        
        return destination_folders

    def format_month(self, month_name):
            # Define a dictionary to map month names to month numbers
        month_mapping = {
            'January': '01 - January',
            'February': '02 - February',
            'March': '03 - March',
            'April': '04 - April',
            'May': '05 - May',
            'June': '06 - June',
            'July': '07 - July',
            'August': '08 - August',
            'September': '09 - September',
            'October': '10 - October',
            'November': '11 - November',
            'December': '12 - December'
        }

        return month_mapping.get(month_name, "Unknown Month")


class FilterManager():

    FILTER_STRINGS = ["\[Second Printing\]", "\[Variant\]", "Special", "Annual", "-1", "Comic"]
    
    def __init__(self):
        self.filter_strings = FilterManager.FILTER_STRINGS
        self.filter_data = None

    def filter(self, data, filter_column):
        return data[~data[filter_column].str.contains('|'.join(self.filter_strings), case=False)]
    
    def add_filter(self, string):
        self.filter_strings.append(string)

    def reset_filter(self):
        self.filter_string = FilterManager.FILTER_STRINGS

class MAWDataManager():

    def __init__(self):
        self.data_fetcher = MAWFetcher()
        self.seriesid = None
        self.active_data = pd.DataFrame()
        self.data_filter = FilterManager()

    def get_active_MAW_data(self):
        return self.active_data
    
    def split_active_data_dates(self):
        self.active_data[['Month', 'Year']] = self.active_data['Cover Date'].str.split(' ', n=1, expand=True)
        return self.active_data

    def load_MAW_data(self):
        if self.seriesid == None:
            print("Series ID has not been set. Please set Series ID.")
            return
        
        if not self.has_existing_data():
            self.fetch_MAW_data()
        else:
            self.active_data = self.get_MAW_data_from_csv()

        return self.active_data
    
    def fetch_MAW_data(self):
            if self.has_existing_data():
                self.delete_existing_MAW_data_csv()

            self.data_fetcher.fetch()
            self.active_data = pd.DataFrame(columns=["Issue Name", "Cover Date"])
            self.active_data["Issue Name"] = self.data_fetcher.issues
            self.active_data["Cover Date"] = self.data_fetcher.cover_dates
            self.write_MAW_data_to_csv()
            return self.active_data

    def filter_active_data(self):
        self.active_data = self.data_filter.filter(self.active_data, self.active_data.columns[0])
        
    def set_series_id(self, sid):
        self.seriesid = sid
        self.data_fetcher.seriesid = sid

    def has_existing_data(self):
        filename = CSVManager.get_csv_from_sid(self.seriesid)
        if filename != None:
            return True
        else:
            return False
    
    def get_existing_data_creation_date(self):
        filename = CSVManager.get_csv_from_sid(self.seriesid)
        creation_date = CSVManager.get_creation_date_from_csv(filename)
        return creation_date

    def get_MAW_data_from_csv(self):
        filename = CSVManager.get_csv_from_sid(self.seriesid)
        MAW_data = CSVManager.get_data_from_csv(filename)
        return MAW_data
    
    def delete_existing_MAW_data_csv(self):
        CSVManager.delete_csv_by_sid(self.seriesid)

    def write_MAW_data_to_csv(self):
        if self.active_data.empty:
            print("No active data to write to CSV, make sure this is being called only from get_MAW_data")
            return
        
        CSVManager.write_to_csv(self.seriesid, issueArray=self.active_data['Issue Name'], dateArray=self.active_data['Cover Date'])

class DriveDataManager():

    def __init__(self):
        self.active_data = pd.DataFrame()
        self.folder_dict = None
        self.monthly_packages_id = None

    def get_active_data(self):
        return self.active_data
    
    def set_folder_data(self, dict):
        self.folder_dict = dict
        return self.folder_dict

    def parse_graph_response_to_data_frame(self, drive_items):
        data_to_concat = []

        for drive_item in drive_items:
            file_name = drive_item['name']
            parent_ref = drive_item['parentReference']
            folder_name = parent_ref['name']
            file_id = drive_item['id']

            data_to_concat.append([file_name, folder_name, file_id])
        
        drive_data = pd.DataFrame(data_to_concat, columns=["File Name", "Folder Name", "File ID"])
        drive_data = drive_data.sort_values(by="File Name")
        self.active_data = drive_data
        return self.active_data
    
    def parse_graph_response_to_monthly_package_folder_id(self, drive_items):
        for drive_item in drive_items:
            if 'name' in drive_item and drive_item['name'] == "Monthly Packages":
                self.monthly_packages_id = drive_item['id']
                return self.monthly_packages_id


    def remove_entry_from_drive_data(self, row_name):
        self.active_data = self.active_data[self.active_data['File Name'] != row_name]
        return self.active_data
    
    def remove_all_entries_after(self, index):
        index = int(index)
        self.active_data = self.active_data.iloc[:index - 1]
        return self.active_data


class CSVManager():

    FILEROOT = "CSVs"

    @staticmethod
    def write_to_csv(sid, issueArray, dateArray):
        fileName = "%s\%s_%s.csv" % (CSVManager.FILEROOT,sid,date.today())
        df = pd.DataFrame({"Issue Name" : issueArray, "Cover Date" : dateArray})
        df.to_csv(fileName, index=False)

    @staticmethod
    def get_csv_from_sid(sid):
        if sid == None:
            return None
        for filename in os.listdir(CSVManager.FILEROOT):
            if filename.startswith(sid+"_"):
                return filename
        
        return None
    
    @staticmethod
    def get_creation_date_from_csv(filename):
        namedata = filename.split("_")
        filedate = namedata[1].replace(".csv", "")
        return filedate
    
    @staticmethod
    def get_sid_from_csv(filename):
        namedata = filename.split("_")
        filesid = namedata[0]
        return filesid
    
    @staticmethod
    def delete_csv(filename):
        os.remove("%s\%s" % (CSVManager.FILEROOT, filename))

    @staticmethod
    def delete_csv_by_sid(sid):
        filename = CSVManager.get_csv_from_sid(sid)
        if filename == None:
            return
        CSVManager.delete_csv(filename)
    
    @staticmethod
    def get_data_from_csv(filename):
        data = pd.read_csv("%s\%s" % (CSVManager.FILEROOT, filename))
        return data