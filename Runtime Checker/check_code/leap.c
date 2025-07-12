#include <stdio.h>

int main(){
    int a;
    printf("Enter a Year: ");
    scanf("%d", &a);
    if ((a % 4 == 0 && a % 100 != 0) || (a % 400 == 0))
        printf("%d is a Leapyear", a);
    else
        printf("%d is not a Leapyear", a);
    return 0;
}