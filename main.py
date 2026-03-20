#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jan 16 13:24:12 2025
@author: harveyfeng1
"""

import pandas as pd
import os
import urllib.request
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from io import StringIO
import ephem
import datetime
import json
import math
import re
import sys
import pytz
from suntime import Sun
import calendar
import holidays

year = 2026
threshold = -0.0  # Replace with your desired tide level, in ft
station_info = {
	'PugetSound': {
		'station_id': '9447130',
		'station': 'Puget Sound',
		'area': 'Seattle',
  		'lat': 47.283,
		'lon': -122.63
	},
	'HalfMoonBay': {
		'station_id': '9414131',
		'station': 'Half Moon Bay Pillar Point',
		'area': 'Bay Area',
		'lat': 37.429,
		'lon': -122.47
	},
	'LosAngeles': {
		'station_id': '9410660',
		'station': 'Los Angeles',
		'area': 'Los Angeles',
		'lat': 34.052,
		'lon': -118.243
	},
	'LongBeach': {
		'station_id': '9410686',
		'station': 'Long Beach',
		'area': 'Los Angeles',
		'lat': 33.77,
		'lon': -118.19
	},
	'CabrilloBeach': {
		'station_id': '9410650',
		'station': 'Cabrillo',
		'area': 'Los Angeles',
		'lat': 34.42,
		'lon': -120.41
	},
	'RedondoBeach': {
		'station_id': '9410738',
		'station': 'Redondo Beach',
		'area': 'Los Angeles',
		'lat': 33.848,
		'lon': -118.41
	},
	'CoyotePointArdvark': {
		'station_id': '9414449',
		'station': 'Coyote Point Ardvark',
		'area': 'Bay Area',
		'lat': 32.848,
		'lon': -117.27
	},
	'SantaCruz': {
		'station_id': '9413745',
		'station': 'Santa Cruz',
		'area': 'Santa Cruz',
		'lat': 36.974,
		'lon': -122.13
	},
	'OceanBeach': {
		'station_id': '9414275',
		'station': 'Ocean Beach',
		'area': 'San Francisco',
		'lat': 33.15,
		'lon': -117.37
	},
	'GoldStreetBridge': {
		'station_id': '9414551',
		'station': 'Upper Guadalupe Slough',
		'area': 'Bay Area',
		'lat': 32.73,
		'lon': -117.13
	},
	'DumbartonPier': {
		'station_id': '9414509',
		'station': 'Dumbarton Pier',
		'area': 'Bay Area',
		'lat': 37.808,
		'lon': -122.43
	},
	'BolinasLagoon': {
		'station_id': '9414958',
		'station': 'Bolinas Lagoon',
		'area': 'Marin',
		'lat': 37.908,
		'lon': -122.69
	},
	'PointReyes': {
		'station_id': '9415020',
		'station': 'Point Reyes',
		'area': 'Marin',
		'lat': 38.048,
		'lon': -122.68
	},
	'Inverness': {
		'station_id': '9415228',
		'station': 'Inverness',
		'area': 'Tomales Bay',
		'lat': 38.058,
		'lon': -122.81
	},
	'BodegaBay': {
		'station_id': '9415625',
		'station': 'Bodega Bay',
		'area': 'Bodega Bay',
		'lat': 38.338,
		'lon': -122.91
	}
}


def _parse_noaa_text(raw_text: str, threshold: float) -> pd.DataFrame:
	"""Strip NOAA header, parse tab-delimited data, and filter by tide threshold."""
	lines = raw_text.splitlines()
	first_empty = next((i for i, line in enumerate(lines) if not line.strip()), None)
	if first_empty is None:
		raise ValueError("No empty row found in NOAA data")
	data_lines = lines[first_empty + 2:]  # skip blank line + column header row
	df = pd.read_csv(StringIO('\n'.join(data_lines)), sep='\t', header=None)
	num_rows, num_columns = df.shape
	print(f"Total rows: {num_rows}, columns: {num_columns}")
	df.iloc[:, 0] = df.iloc[:, 0].str[5:]  # remove year prefix from date column
	print(f"Lowest tide: {df.iloc[:, 3].min():.2f} ft")
	filtered = df[df.iloc[:, 3] <= threshold].drop(df.columns[4:], axis=1)
	return filtered

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

def get_sun_times_on_day(year: int, month: int, day: int, lat: float, lon: float):
	local_timezone = pytz.timezone('US/PACIFIC')

	sun = Sun(lat, lon)
	dst_delta = local_timezone.localize(datetime.datetime(year, month, day)).dst()

	today_sunset = sun.get_sunset_time(at_date=datetime.datetime(year,month,day), time_zone=local_timezone) - dst_delta
	today_sunrise = sun.get_sunrise_time(at_date=datetime.datetime(year,month,day), time_zone=local_timezone) - dst_delta

	# need to replace since sometimes the sunset date is off by 1 (dst?)
	today_sunrise = today_sunrise.replace(year=year, month=month, day=day)
	today_sunset = today_sunset.replace(year=year, month=month, day=day)

	return today_sunrise, today_sunset

# collapse the lowtide time, date and year into a single pandas timestamp
# adds a new column with the timestamp
def collapse_to_datetime(df: pd.DataFrame, year: int) -> None:
	dates = []
	for row in range(df.shape[0]):
		df_row = df.iloc[row]
		time = datetime.datetime.strptime(f"{df_row['date']}/{year} {df_row['time']}", "%m/%d/%Y %I:%M %p")
		dates.append(pd.Timestamp(time).tz_localize('US/PACIFIC', ambiguous=True))
	df['low_tide_time'] = dates

# create 3 new columns with sunrise, sunset and moon illumination information
def add_sun_moon_info(df: pd.DataFrame, lat: float, lon: float) -> None:
	moon_illumination, sunrise, sunset = [], [], []
	for t in df['low_tide_time']:
		yr, month, day = t.year, t.month, t.day
		moon_illumination.append(get_moon_illumination_on_day(yr, month, day))
		srise, sset = get_sun_times_on_day(yr, month, day, lat, lon)
		sunrise.append(srise)
		sunset.append(sset)
	df['moon_illumination'] = moon_illumination
	df['sunrise'] = sunrise
	df['sunset'] = sunset

# label each date as ['night', 'workday', 'holiday', 'weekend'] by checking its condition
def add_date_label(df: pd.DataFrame) -> None:
	# checks if lowtide is within 1.5 hours of sunrise or sunset
	def is_low_tide_at_night(row: pd.Series) -> bool:
		if abs((row['sunrise'] - row['low_tide_time']).total_seconds()) / 3600 < 1.5:
			return False
		if abs((row['low_tide_time'] - row['sunset']).total_seconds()) / 3600 < 1.5:
			return False
		if row['low_tide_time'] > row['sunrise'] and row['low_tide_time'] < row['sunset']:
			return False
		return True

	def is_low_tide_not_during_work_time(row: pd.Series) -> bool:
		work_start, work_end = row['low_tide_time'].replace(hour=10, minute=0), row['low_tide_time'].replace(hour=17, minute=0)
		if work_start.hour - row['low_tide_time'].hour >= 2:
			return True
		if row['low_tide_time'].hour - work_end.hour >= 1:
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

def _responsive_script() -> str:
	return """
const MONTH_NAMES = ['January','February','March','April','May','June',
                     'July','August','September','October','November','December'];

function calcLayout(cols, rows) {
    const hSpacing = cols > 1 ? 0.04 : 0;
    const vSpacing = rows <= 4 ? 0.10 : rows <= 6 ? 0.07 : 0.05;
    const colWidth  = (1 - hSpacing  * (cols - 1)) / cols;
    const rowHeight = (1 - vSpacing * (rows - 1)) / rows;
    const fontSize  = Math.max(14, 22 - rows);

    let update = { height: window.innerHeight - 20, width: window.innerWidth, autosize: false };
    let annotations = [];

    for (let month = 1; month <= 12; month++) {
        const r = Math.floor((month - 1) / cols);
        const c = (month - 1) % cols;
        const xStart = c * (colWidth + hSpacing);
        const xEnd   = xStart + colWidth;
        const yEnd   = 1 - r * (rowHeight + vSpacing);
        const yStart = yEnd - rowHeight;
        const axKey  = month === 1 ? '' : String(month);
        update['xaxis' + axKey + '.domain'] = [xStart, xEnd];
        update['yaxis' + axKey + '.domain'] = [yStart, yEnd];
        annotations.push({
            text: MONTH_NAMES[month - 1],
            x: (xStart + xEnd) / 2, y: yEnd + 0.005,
            xref: 'paper', yref: 'paper',
            xanchor: 'center', yanchor: 'bottom',
            showarrow: false, font: { size: fontSize }
        });
    }
    update['annotations'] = annotations;
    return update;
}

function updateLayout() {
    const div = document.getElementById('tide-chart');
    if (!div) return;
    const w = window.innerWidth;
    let cols, rows;
    if      (w >= 1200) { cols = 3; rows = 4; }
    else if (w >=  700) { cols = 2; rows = 6; }
    else                { cols = 2; rows = 6; }
    Plotly.relayout(div, calcLayout(cols, rows));
}

updateLayout();
window.addEventListener('resize', updateLayout);
document.body.style.overflowX = 'hidden';
document.body.style.margin = '0';
"""

def _build_summary_html(df: pd.DataFrame, station_area: str) -> str:
	color_lut = {
		'night'  			: '#000000',
		'workday'			: '#D55E00',
		'holiday'			: '#E69F00',
		'weekend'			: '#00C853',
		'before/after work'	: '#56B4E9',
	}

	tides = df[df['low_tide'] < -0.5].sort_values('low_tide')

	rows_html = ''.join(
		f"""<tr style="background:{'#f7f7f7' if i % 2 == 0 else 'white'}">
			<td style="padding:7px 10px">{r['low_tide_time'].strftime('%a %b %-d')}</td>
			<td style="padding:7px 10px">{r['low_tide']:.2f}</td>
			<td style="padding:7px 10px">{r['low_tide_time'].strftime('%-I:%M %p')}</td>
			<td style="padding:7px 10px; color:{color_lut.get(r['label'], '#888')}; font-weight:600">{r['label']}</td>
			<td style="padding:7px 10px">{r['moon_illumination']:.0f}%</td>
			<td style="padding:7px 10px">{r['sunrise'].strftime('%-I:%M %p')}</td>
			<td style="padding:7px 10px">{r['sunset'].strftime('%-I:%M %p')}</td>
		</tr>"""
		for i, (_, r) in enumerate(tides.iterrows())
	)

	return f"""
<details style="margin:24px 16px; font-family:sans-serif;">
	<summary style="cursor:pointer; font-size:15px; font-weight:bold; padding:10px 16px;
		background:#2d2d2d; color:white; border-radius:6px; list-style:none; display:flex;
		justify-content:space-between; align-items:center;">
		<span>All Low Tides &lt; -0.5 ft — {year} {station_area}</span>
		<span style="font-weight:normal; font-size:13px">{len(tides)} tides ▼</span>
	</summary>
	<div style="max-height:420px; overflow-y:auto; border:1px solid #ddd; border-top:none; border-radius:0 0 6px 6px;">
		<table style="width:100%; border-collapse:collapse; font-size:13px;">
			<thead>
				<tr style="background:#2d2d2d; color:white; position:sticky; top:0; z-index:1;">
					<th style="padding:8px 10px; text-align:left">Date</th>
					<th style="padding:8px 10px; text-align:left">Tide (ft)</th>
					<th style="padding:8px 10px; text-align:left">Time</th>
					<th style="padding:8px 10px; text-align:left">Type</th>
					<th style="padding:8px 10px; text-align:left">Moon</th>
					<th style="padding:8px 10px; text-align:left">Sunrise</th>
					<th style="padding:8px 10px; text-align:left">Sunset</th>
				</tr>
			</thead>
			<tbody>{rows_html}</tbody>
		</table>
	</div>
</details>
"""

def plotly_plot(df: pd.DataFrame, station_name: str, station_area: str) -> None:
	rows = 4
	cols = 3
	month_names = calendar.month_name[1:]
	min_tide = df['low_tide'].min()
	print(min_tide)

	color_lut = {
		'night'  			: '#000000',  # black
		'workday'			: '#CC79A7',  # reddish purple
		'holiday'			: '#E69F00',  # orange
		'weekend'			: '#00C853',  # vivid green
		'before/after work'	: '#56B4E9',  # sky blue
	}

	fig = make_subplots(
		rows=rows,
		cols=cols,
		subplot_titles=month_names,
		horizontal_spacing = 0.03,
		vertical_spacing=0.08
	)

	emoji_lut = {
		'morning' : '💤',
		'daytime' : '☀️',
	}

	def time_emoji(r) -> str:
		if r['label'] == 'night':
			return ''
		return emoji_lut['morning'] if r['low_tide_time'].hour < 12 else emoji_lut['daytime']

	# traversing through each possible label for the legend
	shown_legends = []

	# pre-build {month: {day: emoji}} so x-axis ticks can embed emojis
	day_emojis: dict = {}
	for _, r in df.iterrows():
		m, d = r['low_tide_time'].month, r['low_tide_time'].day
		day_emojis.setdefault(m, {})[d] = time_emoji(r)

	for label in df['label'].unique():
		for row in range(rows):
			for col in range(cols):
				month = row * cols + col + 1
				filter_df = df[(df['low_tide_time'].dt.month == month) & (df['label'] == label)]

				colors = [color_lut[label] for label in filter_df['label']]
				hovertext = [
					f"""
Low tide time: {r['low_tide_time'].strftime('%a %m/%d/%Y %I:%M %p')}<br>
Low tide: {r['low_tide']} ft<br>
Sunrise time: {r['sunrise'].strftime('%I:%M %p')}<br>
Sunset time: {r['sunset'].strftime('%I:%M %p')}<br>
Moon Illumination: {r['moon_illumination']:.0f}%<br>
Label: {r['label']}
					"""
					for _, r in filter_df.iterrows()
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
						hoverinfo='text',
						legendgroup=f'{(row+1) * (col+1)}',
						showlegend=show_legend,
					),
					row=row+1,
					col=col+1,
				)

				if show_legend:
					shown_legends.append(label)

	# add emoji legend entries as invisible traces
	for key, (description) in [
		('morning', '🐓 Morning (before noon)'),
		('daytime', '☀️ Daytime (noon and after)'),
	]:
		fig.add_trace(go.Scatter(
			x=[None], y=[None],
			mode='markers',
			marker=dict(size=0, color='rgba(0,0,0,0)'),
			name=description,
			showlegend=True,
			legendgroup='emoji',
		), row=1, col=1)

	# update axis ranges for each subplot
	for row in range(rows):
		for col in range(cols):
			month = row * cols + col + 1
			filter_df = df[df['low_tide_time'].dt.month == month]
			tick_vals = sorted(set([1] + list(filter_df['low_tide_time'].dt.day) + [calendar.monthrange(year, month)[1]]))
			tick_text = [
				f"{d}\n{day_emojis.get(month, {}).get(d, '')}" if day_emojis.get(month, {}).get(d) else str(d)
				for d in tick_vals
			]
			fig.update_xaxes(
				tickvals=tick_vals,
				ticktext=tick_text,
				tickangle=90,
				range=[0, calendar.monthrange(year, month)[1]+1],
				row=row+1,
				col=col+1
			)
			fig.update_yaxes(
				range=[min_tide - 0.1, 0],
				row=row+1,
				col=col+1
			)

	fig.update_layout(
		autosize=True,
		title_text=f"{list(df['low_tide_time'])[0].year} {station_area} Low Tides",
		barcornerradius=15,
		legend_tracegroupgap=0
	)
	fig.update_annotations(font_size=20)

	output_path = f"tideplot_{year}_{station_name.lower()}.html"
	with open(output_path, 'w') as f:
		f.write(fig.to_html(
			div_id='tide-chart',
			full_html=True,
			include_plotlyjs='cdn',
			config={'responsive': True},
			post_script=_responsive_script(),
		))
		f.write(_build_summary_html(df, station_area))

def geocode_location(query: str) -> tuple[float, float, str]:
	from geopy.geocoders import Nominatim
	geolocator = Nominatim(user_agent='tidepool2')
	location = geolocator.geocode(query)
	if not location:
		raise ValueError(f"Could not find location: '{query}'")
	print(f"Geocoded '{query}' → {location.address}")
	return location.latitude, location.longitude, location.address

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
	R = 6371
	dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
	a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
	return R * 2 * math.asin(math.sqrt(a))

def find_nearest_noaa_station(lat: float, lon: float) -> dict:
	url = 'https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?type=tidepredictions'
	with urllib.request.urlopen(url) as resp:
		stations = json.loads(resp.read())['stations']
	nearest = min(stations, key=lambda s: _haversine_km(lat, lon, float(s['lat']), float(s['lng'])))
	dist = _haversine_km(lat, lon, float(nearest['lat']), float(nearest['lng']))
	print(f"Nearest NOAA station: {nearest['name']} ({nearest['id']}) — {dist:.1f} km away")
	return {
		'station_id': nearest['id'],
		'station':    nearest['name'],
		'area':       nearest.get('state', nearest['name']),
		'lat':        float(nearest['lat']),
		'lon':        float(nearest['lng']),
	}

def search_and_plot(query: str) -> dict:
	lat, lon, address = geocode_location(query)
	info = find_nearest_noaa_station(lat, lon)
	key = re.sub(r'[^a-zA-Z0-9]', '', info['station'])
	info['query'] = query
	station_info[key] = info
	main(key)
	return {
		'key':     key,
		'address': address,
		'station': info['station'],
	}

def main(station_name: str) -> None:
	station_id = station_info[station_name]['station_id']
	station_area = station_info[station_name]['area']
	location_label = station_info[station_name].get('query', station_area)
	lat = station_info[station_name]['lat']
	lon = station_info[station_name]['lon']

	start_date = f'{year}0101'
	end_date = f'{year}1231'
	url = f'https://tidesandcurrents.noaa.gov/cgi-bin/predictiondownload.cgi?&stnid={station_id}&threshold=&thresholdDirection=&bdate={start_date}&edate={end_date}&units=standard&timezone=LST/LDT&datum=MLLW&interval=hilo&clock=12hour&type=txt&annual=false'
	print(url)

	cache_file = f'tides_{year}_{station_name.lower()}.txt'
	if os.path.exists(cache_file):
		print(f"Cache hit: {cache_file}")
		with open(cache_file, 'r') as f:
			raw_text = f.read()
	else:
		print('Downloading data from NOAA...')
		with urllib.request.urlopen(url) as resp:
			raw_text = resp.read().decode('utf-8')
		with open(cache_file, 'w') as f:
			f.write(raw_text)
		print(f"Data cached to {cache_file}")

	df = _parse_noaa_text(raw_text, threshold)
	df = df.rename(columns={0: 'date', 1: 'day_of_week', 2: 'time', 3: 'low_tide'})

	collapse_to_datetime(df, year)
	del df['date']
	del df['day_of_week']
	del df['time']

	add_sun_moon_info(df, lat, lon)
	add_date_label(df)

	plotly_plot(df, station_name, location_label)

if __name__ == '__main__':
	for key in station_info:
		main(key)
