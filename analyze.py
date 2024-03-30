import pandas as pd
df = pd.read_csv('data.csv')
print(df.describe()) 
print('Oldest person is', df.loc[df['age'].idxmax()]['name'])
