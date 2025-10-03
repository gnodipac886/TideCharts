#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jan 16 13:24:12 2025
@author: harveyfeng1
""" 

import pandas as pd
import os
import urllib.request
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import csv
import ephem
import datetime
import pytz
from suntime import Sun
import calendar
import holidays

year = '2026'
threshold = -0.0  # Replace with your desired tide level, in ft
station_info = {
	'PugetSound': {
		'station_id': '9447130',
		'station': 'Puget Sound', 
		'area': 'Seattle',
  		'lat': 47.283, 
		'long': -122.63
	},
	'HalfMoonBay': {
		'station_id': '9414131',
		'station': 'Half Moon Bay Pillar Point', 
		'area': 'Bay Area',
		'lat': 37.429, 
		'lon': -122.47
	}
}
station_name = 'PugetSound'
# station_name = 'HalfMoonBay'
station_id = station_info[station_name]['station_id']
station_area = station_info[station_name]['area']

def find_first_empty_row(filename):
	with open(filename, 'r') as file:
		lines = file.readlines()

	for i, line in enumerate(lines, start=1):
		if not line.strip():  # If the line is empty or contains only whitespace
			return i  # Return the line number of the first empty row

	return None  # Return None if no empty row is found


def remove_first_x_rows(filepath, filename, newfile, x):
	# Read the entire file
	with open(os.path.join(filepath, filename), 'r') as file:
		lines = file.readlines()

	# Skip the first 'x' rows and get the rest of the lines
	new_lines = lines[x+1:]

	# Write the remaining lines back to the same file or a new file
	with open(os.path.join(filepath, newfile), 'w+') as file:
		file.writelines(new_lines)
		


def txt_to_csv(txt_filename, csv_filename, delimiter='\t'):
	with open(txt_filename, 'r') as txt_file:
		# Read the contents of the .txt file
		lines = txt_file.readlines()
		
	# Open the .csv file for writing
	with open(csv_filename, 'w', newline='') as csv_file:
		csv_writer = csv.writer(csv_file)
		
		# Write each line of the .txt file as a row in the .csv file
		for line in lines:
			# Split the line into columns by tab and write to CSV
			csv_writer.writerow(line.strip().split(delimiter))

	print(f"Converted {txt_filename} to {csv_filename}")


def plot_time_dates(df,x):
	column_1 = df.iloc[:, 0]  # First column
	column_4 = df.iloc[:, 3]  # Fourth column
	# Create a bar chart using the first and fourth columns
	plt.bar(column_1, column_4, color='blue')
	  
	  # Add labels and title
	plt.xlabel('Dates with low tide')  # Label for the x-axis
	#plt.ylabel('Tide')  # Label for the y-axis
	plt.title(f'{year} Low Tide ft vs Dates')
	plt.xticks(column_1[::5],  rotation='vertical')
	plt.locator_params(axis='x', nbins=x) # number of dates you want to put there to avoid too dense
	# Show the plot
	plt.show()
	
  
def filter_dates(input_file, output_file, threshold):
	# Read the CSV file into a pandas DataFrame
	df = pd.read_csv(input_file, header=None)
	num_rows, num_columns = df.shape
	print(f"Total rows: {num_rows}")
	print(f"Total columns: {num_columns}")
	
	df.iloc[:, 0] = df.iloc[:, 0].str[5:] # remove all colomns after the tide
	print(df)
	
	# Keep rows where the 4th column (index 3), the tide < threshold
	filtered_df = df[df.iloc[:, 3] <= threshold]
	filtered_df = filtered_df.drop(df.columns[4:], axis=1) # modify the date, remove the year
	print (f"lowest tide in {year} is ", df.iloc[:, 3].min(), "ft") # find the lowest tide

	# show the result
	return filtered_df

def get_moon_illumination_on_day(year: int, month: int, day: int):
	"""Returns a floating-point number from 0-1. where 0=new, 0.5=full, 1=new"""
	#Ephem stores its date numbers as floating points, which the following uses
	#to conveniently extract the percent time between one new moon and the next
	#This corresponds (somewhat roughly) to the phase of the moon.

	#Use Year, Month, Day as arguments
	date = ephem.Date(datetime.date(year,month,day))

	nnm = ephem.next_new_moon(date)
	pnm = ephem.previous_new_moon(date)

	lunation = (date-pnm)/(nnm-pnm)

	#Note that there is a ephem.Moon().phase() command, but this returns the
	#percentage of the moon which is illuminated. This is not really what we want.

	# returns percent illumination 0-100
	return 100*(1 - abs(lunation - 0.5) / 0.5)

def get_sun_times_on_day(year,month,day):
	# Get your local timezone
	local_timezone = pytz.timezone('US/PACIFIC')

	# Replace with your latitude and longitude
	latitude = 37.7749 
	longitude = -122.4194

	sun = Sun(latitude, longitude)
	dst_delta = local_timezone.localize(datetime.datetime(year, month, day)).dst()

	today_sunset = sun.get_sunset_time(at_date=datetime.datetime(year,month,day), time_zone=local_timezone) - dst_delta
	today_sunrise = sun.get_sunrise_time(at_date=datetime.datetime(year,month,day), time_zone=local_timezone) - dst_delta

	# need to replace since sometimes the sunset date is off by 1 (dst?)
	today_sunrise = today_sunrise.replace(year=year, month=month, day=day)
	today_sunset = today_sunset.replace(year=year, month=month, day=day)
 
	return today_sunrise, today_sunset

# collapse the lowtide time, date and year into a single pandas timestamp
# adds a new column with the timestamp
def collapse_to_datetime(df:pd.DataFrame, year:int) -> None:
	dates = []
	for row in range(df.shape[0]):
		df_row = df.iloc[row]
		time = datetime.datetime.strptime(f"{df_row['date']}/{year} {df_row['time']}", "%m/%d/%Y %I:%M %p")
		dates.append(pd.Timestamp(time).tz_localize('US/PACIFIC', ambiguous=True))
	df['low_tide_time'] = dates

# create 3 new columns with sunrise, sunset and moon illumination information
def add_sun_moon_info(df: pd.DataFrame) -> None:
	moon_illumination, sunrise, sunset = [], [], []
	for t in df['low_tide_time']:
		month, day, year = t.month, t.day, t.year
		moon_illumination.append(get_moon_illumination_on_day(year, int(month), int(day)))
		srise, sset = get_sun_times_on_day(year, int(month), int(day))
		sunrise.append(srise)
		sunset.append(sset)
	df['moon_illumination'] = moon_illumination
	df['sunrise'] = sunrise
	df['sunset'] = sunset
	
# label each date as ['night', 'workday', 'holiday', 'weekend'] by checking its condition
def add_date_label(df: pd.DataFrame) -> None:
	# checks if lowtide is within 1 hour of sunrise or sunset
	def is_low_tide_at_night(df:pd.DataFrame) -> bool:
		if (df['sunrise'] - df['low_tide_time']).seconds / 3600 < 1.5:
			return False
		if (df['low_tide_time'] - df['sunset']).seconds / 3600 < 1.5:
			return False
		if df['low_tide_time'] > df['sunrise'] and df['low_tide_time'] < df['sunset']:
			return False
		return True

	def is_low_tide_not_during_work_time(df: pd.DataFrame) -> bool:
		work_start, work_end = df['low_tide_time'].replace(hour=10, minute=0), df['low_tide_time'].replace(hour=17, minute=0)
		if work_start.hour - df['low_tide_time'].hour >= 2:
			# print(df['low_tide_time'], work_start.hour - df['low_tide_time'].hour)
			return True
		if df['low_tide_time'].hour - work_end.hour >= 1:
			# print(df['low_tide_time'], df['low_tide_time'].hour - work_end.hour)
			return True
		return False
	
	us_holidays = holidays.US(years=df.iloc[0]['low_tide_time'].year)
		
	label = []
	for _, row in df.iterrows():
		# check if low tide is at night
		if is_low_tide_at_night(row):
			label.append('night')
			continue
			
		# check if date is on a weekend
		if row['low_tide_time'].isoweekday() in [6, 7]:
			label.append('weekend')
			continue
		
		# check if date is on a US holiday
		if row['low_tide_time'] in us_holidays:
			label.append('holiday')
			continue

		if is_low_tide_not_during_work_time(row):
			label.append('before/after work')
			continue
		
		label.append('workday')
		
	df['label'] = label
	
def plotly_plot(df: pd.DataFrame) -> None:
	# Create figure with 2 subplots
	rows = 4
	cols = 3
	month_names = calendar.month_name[1:]
	min_tide = df['low_tide'].min()
	print(min_tide)

	color_lut = {
		'night'  			: 'black', 
		'workday'			: 'red', 
		'holiday'			: 'orange', 
		'weekend'			: 'green',
		'before/after work'	: 'blue'
	}

	fig = make_subplots(
		rows=rows, 
		cols=cols,
		subplot_titles=month_names,
		horizontal_spacing = 0.03,
		vertical_spacing=0.08
	)

	# traversing through each possible label for the legend
	shown_legends = []
	for label in df['label'].unique():
		for row in range(rows):
			for col in range(cols):
				month = row * cols + col + 1
				filter_df = df[(df['low_tide_time'].dt.month == month) & (df['label'] == label)]
				
				colors = [color_lut[label] for label in filter_df['label']]
				hovertext = [
					f"""
Low tide time: {row['low_tide_time'].strftime('%a %m/%d/%Y %I:%M %p')}<br>
Low tide: {row['low_tide']} ft<br>
Sunrise time: {row['sunrise'].strftime('%I:%M %p')}<br>
Sunset time: {row['sunset'].strftime('%I:%M %p')}<br>
Moon Illumination: {row['moon_illumination']:.0f}%<br>
Label: {row['label']}
					"""
					for _, row in filter_df.iterrows()
				]
				
				# since some months there are no low tides with the given label, we don't want to show a legend for it
				show_legend = label not in shown_legends and list(filter_df['low_tide']) != []

				fig.add_trace(
					go.Bar(
						x=filter_df['low_tide_time'].dt.day, 
						y=filter_df['low_tide'],
						name=f"{label}",
						marker_color=colors,
						hovertext=hovertext,
						legendgroup = f'{(row+1) * (col+1)}',
						showlegend = show_legend # we want a custom legend for the possible labels
					),
					row=row+1, 
					col=col+1,
				)
				
				if show_legend:
					shown_legends.append(label)
				
	# update axis ranges for each subplot
	for row in range(rows):
		for col in range(cols):
			month = row * cols + col + 1
			filter_df = df[df['low_tide_time'].dt.month == month]
			x_ticks = set([1] + list(filter_df['low_tide_time'].dt.day) + [calendar.monthrange(int(year), month)[1]])
			fig.update_xaxes(
				tickvals=list(x_ticks),
				range=[0, calendar.monthrange(int(year), month)[1]+1],
				row=row+1, 
				col=col+1
			)
			fig.update_yaxes(
				range=[min_tide - 0.1,0],
				row=row+1, 
				col=col+1
			)

	fig.update_layout(
		height=1100, 
		width=2000, 
		title_text=f"{list(df['low_tide_time'])[0].year} {station_area} Low Tides",
		barcornerradius=15,
		legend_tracegroupgap=0 # make gap between legend groups 0 to seem like a single legend
		# showlegend=False
	)
	# fig.show()
	fig.write_html(f"tideplot_{year}_{station_name.lower()}.html")

if __name__ == '__main__':
	# setup meta vars for url
	start_date = f'{year}0101'
	end_date = f'{year}1231'
	url = f'https://tidesandcurrents.noaa.gov/cgi-bin/predictiondownload.cgi?&stnid={station_id}&threshold=&thresholdDirection=&bdate={start_date}&edate={end_date}&units=standard&timezone=LST/LDT&datum=MLLW&interval=hilo&clock=12hour&type=txt&annual=false'
	print(url)
	# save the file downloaded from NOAA to tides.txt
	filename = f'tides_{year}_{station_name.lower()}.txt' 
	filepath = os.getcwd()

	txt_filename = '1.txt'
	csv_filename = '1.csv'

	# check if the file is already there
	if os.path.exists(os.path.join(filepath, filename)):
		print(f"File {filename} already exists.  Skipping download.")
	else:
		# download the data from NOAA
		print('Downloading data from NOAA...')
		print(f'url: {url}')
		filename, _ = urllib.request.urlretrieve(url, filename)
		print(f"Data saved to {filename}")

	#  remove the first empty row
	first_empty_row = find_first_empty_row(os.path.join(filepath, filename))
	remove_first_x_rows(filepath, filename, txt_filename ,first_empty_row)
	print(f"First {first_empty_row } rows removed from {filename}.")

	if first_empty_row:
		print(f"The first empty row is: {first_empty_row}")
	else:
		print("No empty rows found.")

	txt_to_csv(os.path.join(filepath, txt_filename), os.path.join(filepath, csv_filename), delimiter='\t')

	input_file = os.path.join(filepath, csv_filename) # name the tide csv to 1.csv
	output_file = os.path.join(filepath, f'dates_low_tides_{year}_{station_name.lower()}.csv')

	print("File path:", filepath)
	if os.access(filepath, os.R_OK):
		print("File is readable")
	else:
		print("File is not readable")
	print ("Only dates with tide <= ", threshold , " are left")
		
	df = filter_dates(input_file, output_file, threshold)
	df = df.rename(columns={
		0: 'date',
		1: 'day_of_week',
		2: 'time',
		3: 'low_tide'
	})

	collapse_to_datetime(df, year)
	del df['date']
	del df['day_of_week']
	del df['time']
	
	add_sun_moon_info(df)
	add_date_label(df)

	# Save the filtered DataFrame to a new CSV file
	df.to_csv(output_file, index=False) 
	
	plotly_plot(df)