#!/usr/bin/python3
# -*- coding: utf-8 -*-
import dash
import dash_table
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import requests, json, subprocess, prestodb, time
from kafka import KafkaConsumer, TopicPartition



################################################################################
###
### Nav Bar
###
################################################################################

PLOTLY_LOGO = "https://images.plot.ly/logo/new-branding/plotly-logomark.png"

nav_item = dbc.NavItem(dbc.NavLink("Link", href="#"))
navbar = dbc.Navbar(
    dbc.Container(
        [
            html.A(
                # Use row and col to control vertical alignment of logo / brand
                dbc.Row(
                    [
                        dbc.Col(html.Img(src=PLOTLY_LOGO, height="50px")),
                        dbc.Col(dbc.NavbarBrand("Product Metrics Platform", className="ml-2")),
                    ],
                    align="true",
                    no_gutters=True,
                ),
                href="https://plot.ly",
            ),
            dbc.NavbarToggler(id="navbar-toggler2"),
            dbc.Collapse(
                dbc.Nav(
                    [nav_item], className="ml-auto", navbar=True
                ),
                id="navbar-collapse2",
                navbar=True,
            ),
        ]
    ),
    color="dark",
    dark=True,
    className="mb-5",
)
################################################################################
###
### APP Start
###
################################################################################
# external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
# app = dash.Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])
# app = dash.Dash(external_stylesheets=[dbc.themes.JOURNAL])
app = dash.Dash(external_stylesheets=[dbc.themes.SKETCHY])

# app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

app.layout = html.Div([
    navbar,
    # html.H1(children='Product Metrics Platform'),

    html.Div(children='''
        Product Metrics Platform: A web application to discover and explore predefined metrics fast and easily.
    '''),

    ###########################################################################
    html.H3(children='Select a predefined metric and see result: '),
    dcc.Dropdown(
        id='my-dropdown',
        options=[
            {
                'label': 'Top 10 Tags',
                'value': 'select tag_name, cnt from dim_tags limit 10',
            },
            {
                'label': 'Posts Per Year (Slow About  ~1 min)',
                'value': "select SUBSTR(creation_date,1,4) as year, count(1) as cnt from dim_posts group by 1 order by year"
            },
        ],
        placeholder="Select a metric",
        value='',
    ),
    # LINE CHART
    dcc.Graph(
        id='graph_line',
        config={
            'showSendToCloud': True,
            'plotlyServerURL': 'https://plot.ly'
        }
    ),
    # BAR CHART
    dcc.Graph(
        id='graph_bar',
        config={
            'showSendToCloud': True,
            'plotlyServerURL': 'https://plot.ly'
        }
    ),
    ###########################################################################
    html.H3(children='Compare Presto and Druid Speed:'),
    html.Div(children='''
        Try type "select count(1) from dim_posts" and see the differences..
    '''),
    dcc.Textarea(
        id="sql-state",
        placeholder='Enter a SQL query... eg: select * from sample limit 10',
        style={'width': '60%'}
    ),
    html.Button(id='submit-button', n_clicks=0, children='Submit'),
    html.H3(children='Presto Result:'),
    html.Div(id='presto-state'),
    html.P(),
    html.H3(children='Druid Result: '),
    html.Div(id='druid-state'),
    html.P(),

    ###########################################################################
])


################################################################################
###
### CALLBACKS
###
################################################################################
# Graph Line and Graph Bar Call Back
@app.callback(
    [dash.dependencies.Output('graph_line', 'figure'),
    dash.dependencies.Output('graph_bar', 'figure')],
    [dash.dependencies.Input('my-dropdown', 'value')])
def update_bar_output(value):
    # sql = "select SUBSTR(creation_date,1,4) as year, count(1) as cnt from dim_posts group by 1 order by year"
    # sql = "select tag_name, cnt from dim_tags limit 10"

    rows, dur = exec_presto(value)
    # print("rows: ", rows)

    x_values = [ row[0] for row in rows ]
    y_values = [ row[1] for row in rows ]
    result_line = {
        'data': [{
            'type': 'scatter',
            'x': x_values,
            'y': y_values,
        }],
        'layout': {
            'title': 'Query "{}" finished in {} seconds.'.format(value, dur)
        }
    }

    result_bar = {
        'data': [
            go.Bar(
                x=x_values,
                y=y_values,
                name='Bar',
                marker=go.bar.Marker(
                    color='rgb(55, 83, 109)'
                )
            ),
        ],
        'layout': go.Layout(
            title='Bar Chart',
            showlegend=True,
            legend=go.layout.Legend(
                x=0,
                y=1.0
            ),
            margin=go.layout.Margin(l=40, r=0, t=40, b=30)
        ),
    }
    return result_line, result_bar


# Comparing Presto and Druid for the same query
@app.callback(Output('presto-state', 'children'),
              [Input('submit-button', 'n_clicks')],
              [State('sql-state', 'value'),])
def get_presto_state(n_clicks, sql):
    # Remove semicolons if any
    if not sql: 
        return ''
    sql = sql.replace(';', '') 

    presto_result, dur = exec_presto(sql)

    return u'''
        The Button has been pressed {} times,
        SQL is "{}",
        Query finished in {} seconds,
        Result is: "{}".
    '''.format(n_clicks, sql, dur, presto_result)


@app.callback(Output('druid-state', 'children'),
              [Input('submit-button', 'n_clicks')],
              [State('sql-state', 'value'),])
def get_druid_state(n_clicks, sql):
    if not sql:
        return ''
    sql = sql.replace(';', '')

    druid_result, dur = exec_druid(sql)

    return u'''
        The Button has been pressed {} times,
        SQL is "{}",
        Query finished in {} seconds,
        Result is: "{}".
    '''.format(n_clicks, sql, dur, druid_result)



################################################################################
###
### FUNCTIONS
###
################################################################################
def exec_presto(sql):
    start = time.clock()
    if not sql or len(sql) == 0:
        return [], 0
    # Demo Only. Should come from a config file
    conn=prestodb.dbapi.connect(
        host='localhost',
        port=8889,
        user='hadoop',
        catalog='hive',
        schema='web',
    )
    cur = conn.cursor()
    cur.execute(sql)
    result = cur.fetchall()
    return result, time.clock() - start
    

def exec_druid(sql):
    start = time.clock()
    msg = json.dumps({'query': sql})
    # print("msg: ", msg)
    headers = {
        'content-type':'application/json'
    }
    
    # Demo Only. Should come from a config file
    druid_url = 'http://34.211.45.55:8082/druid/v2/sql/'
    r = requests.post(url=druid_url, data=msg, headers=headers)
    # print("r: ", r, r.text)
    return r.text, time.clock() - start
    
    

################################################################################
###
### RUN
###
################################################################################
if __name__ == '__main__':
    # Since it is demo, running on port 80 directly
    app.run_server(debug=True, host='0.0.0.0', port=80)
