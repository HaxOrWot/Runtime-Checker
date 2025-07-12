# Python Calculator

operator = input('Enter an operator (+, -, *, /): ')

num1 = float(input('Enter the first num: '))
num2 = float(input('Enter the second num: '))

if operator == '+':
    result = num1 + num2
    print(round(result, 2))
elif operator == '-':
    result = num1 - num2
    print(round(result, 2))
elif operator == '*':
    result = num1 * num2
    print(round(result, 2))
elif operator == '/':
    result = num1 / num2
    print(round(result, 2))
else:
    print(f'"{operator}" is not a valid operator')