package middlewares

import (
 	"fmt"
 	"tollbox_be/inits"
 	"tollbox_be/models"
 	"net/http"
 	"os"
 	"time"

 	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
)

func RequireAuth(ctx *gin.Context) {
	tokenString, err := ctx.Cookie("Authorization")
	if err != nil {
		ctx.JSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
		ctx.Abort()
		return
	}

	token, err := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		return []byte(os.Getenv("SECRET")), nil
	})

	if claims, ok := token.Claims.(jwt.MapClaims); ok && token.Valid {
		if float64(time.Now().Unix()) > claims["exp"].(float64) {
			ctx.JSON(http.StatusUnauthorized, gin.H{"error": "token expired"})
			ctx.Abort()
			return
		}

		var user models.User
		inits.DB.First(&user, int(claims["id"].(float64)))
		if user.ID == 0 {
			ctx.JSON(http.StatusUnauthorized, gin.H{"error": "user not found"})
			ctx.Abort()
			return
		}

		ctx.Set("user", user)
		ctx.Next()
	} else {
		ctx.JSON(http.StatusUnauthorized, gin.H{"error": "invalid token"})
		ctx.Abort()
	}
}

func RequireAdmin(ctx *gin.Context) {
	user, _ := ctx.Get("user") 
	if user.(models.User).Role != 7 {
		ctx.JSON(http.StatusForbidden, gin.H{"error": "Admin only"})
		ctx.Abort()
		return
	}
	ctx.Next()
}
