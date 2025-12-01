
import re

def parse_test():
    content = "cfg.baselinewindow = [0 0.9];"
    pattern = re.compile(r'cfg\.([\w\.]+)\s*=\s*\[([^\]]+)\]')
    matches = pattern.findall(content)
    for match in matches:
        param_name = match[0]
        param_value = match[1]
        print(f"Matched {param_name} with value: {repr(param_value)}")
        
        values = re.findall(r'-?[0-9]+(?:\.[0-9]+)?', param_value)
        print(f"Parsed values: {values}")
        
        if len(values) >= 2:
            val1 = float(values[0])
            val2 = float(values[1])
            print(f"Float values: {val1}, {val2}")
            
            min_val = val1 - 1.0
            max_val = val2 + 1.0
            print(f"Calculated Range: {min_val} to {max_val}")

parse_test()
