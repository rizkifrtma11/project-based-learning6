package routers

import (
	"time"
	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"tollbox_be/controllers"
	"tollbox_be/middlewares"
)

func SetupRouter() *gin.Engine {
	r := gin.Default()

	r.Use(cors.New(cors.Config{
		AllowOrigins:     []string{"http://localhost:8080"},
		AllowMethods:     []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowHeaders:     []string{"Content-Type", "Authorization"},
		AllowCredentials: true,
		MaxAge:           12 * time.Hour,
	}))

	r.POST("/login", controllers.Login)

	r.GET("/users", controllers.GetUsers)
	r.POST("/logout", controllers.Logout)
	r.PUT("/:id", controllers.UpdateUser)
	r.GET("/auth", middlewares.RequireAuth, controllers.Validate)
	r.POST("/signup", middlewares.RequireAuth, middlewares.RequireAdmin, controllers.SignupUser)
	r.DELETE("/:username", middlewares.RequireAuth, middlewares.RequireAdmin, controllers.DeleteUser)

	return r
}
