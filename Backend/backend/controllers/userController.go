package controllers

import (
	//"fmt"
	"net/http"
	"os"
	"time"

	"tollbox_be/inits"
	"tollbox_be/models"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"golang.org/x/crypto/bcrypt"
	//"gorm.io/gorm"
)

// Signup user
func SignupUser(ctx *gin.Context) {
	var body struct {
		Username string `json:"username"`
		Email    string `json:"email"`
		Password string `json:"password"`
		Revive   bool   `json:"revive"` // tanda jika admin ingin revive user
	}

	if err := ctx.BindJSON(&body); err != nil {
		ctx.JSON(400, gin.H{"error": "bad request"})
		return
	}

	var existing models.User

	// Cek user yang soft deleted (Unscoped agar termasuk deleted)
	inits.DB.Unscoped().Where("username = ? OR email = ?", body.Username, body.Email).First(&existing)

	if existing.ID != 0 {
		if existing.DeletedAt.Valid {
			// User pernah dihapus
			if body.Revive {
				// Revive user
				hashed, _ := bcrypt.GenerateFromPassword([]byte(body.Password), 10)
				inits.DB.Unscoped().Model(&existing).Updates(map[string]interface{}{
				    "Password":   string(hashed),
				    "DeletedAt":  nil, // nil untuk menghapus soft delete
				})
				ctx.JSON(200, gin.H{"message": "User berhasil di-revive", "data": existing})
				return
			} else {
				ctx.JSON(409, gin.H{"error": "User pernah dihapus", "option": "reviveOrChange"})
				return
			}
		} else {
			// User aktif
			ctx.JSON(409, gin.H{"error": "Username atau Email sudah terpakai"})
			return
		}
	}

	// Jika user belum ada, buat user baru
	hashed, _ := bcrypt.GenerateFromPassword([]byte(body.Password), 10)
	newUser := models.User{Username: body.Username, Email: body.Email, Password: string(hashed)}
	if err := inits.DB.Create(&newUser).Error; err != nil {
		ctx.JSON(500, gin.H{"error": err.Error()})
		return
	}

	ctx.JSON(200, gin.H{"message": "User baru dibuat", "data": newUser})
}


func Login(ctx *gin.Context) {
	var body struct {
		Username string `json:"username"`
		Password string `json:"password"`
	}

	if ctx.BindJSON(&body) != nil {
		ctx.JSON(400, gin.H{"error": "bad request"})
  		return
 	}

	var user models.User

	result := inits.DB.Where("username = ?", body.Username).First(&user)

	if result.Error != nil {
		ctx.JSON(500, gin.H{"error": "User not found"})
		return
 	}

	err := bcrypt.CompareHashAndPassword([]byte(user.Password), []byte(body.Password))

	if err != nil {
		ctx.JSON(401, gin.H{"error": "unauthorized"})
  		return
 	}

 	token := jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.MapClaims{
  		"id":  user.ID,
  		"exp": time.Now().Add(time.Hour * 24 * 30).Unix(),
 	})

 	tokenString, err := token.SignedString([]byte(os.Getenv("SECRET")))

	 if err != nil {
  		ctx.JSON(500, gin.H{"error": "error signing token"})
  		return
 	}

 	ctx.SetSameSite(http.SameSiteLaxMode)
 	ctx.SetCookie("Authorization", tokenString, 3600*24*30, "/", "localhost", false, true)
}

func GetUsers(ctx *gin.Context) {
	var users []models.User

	err := inits.DB.Select("id", "username", "email", "created_at").Find(&users).Error
	if err != nil {
		ctx.JSON(http.StatusInternalServerError, gin.H{"error": "Error retrieving users"})
		return
	}

	ctx.JSON(http.StatusOK, gin.H{"data": users})
}

func Validate(ctx *gin.Context) {
	user, exists := ctx.Get("user")
	if !exists {
		ctx.JSON(http.StatusInternalServerError, gin.H{"error": "user not found in context"})
		return
	}
	ctx.JSON(http.StatusOK, gin.H{"data": "You are logged in!", "user": user})
}



func Logout(ctx *gin.Context) {
 	ctx.SetSameSite(http.SameSiteLaxMode)
 	ctx.SetCookie("Authorization", "", -1, "", "localhost", false, true)
 	ctx.JSON(200, gin.H{"data": "You are logged out!"})
}

// Update user
func UpdateUser(ctx *gin.Context) {
	var body struct {
		Username string `json:"username"`
		Email    string `json:"email"`
		Password string `json:"password"`
	}

	if err := ctx.BindJSON(&body); err != nil {
		ctx.JSON(http.StatusBadRequest, gin.H{"error": "Invalid input"})
		return
	}

	var user models.User
	if err := inits.DB.First(&user, ctx.Param("id")).Error; err != nil {
		ctx.JSON(http.StatusNotFound, gin.H{"error": "User not found"})
		return
	}

	updates := map[string]interface{}{}

	if body.Username != "" {
		updates["username"] = body.Username
	}
	if body.Email != "" {
		updates["email"] = body.Email
	}
	if body.Password != "" {
		hash, err := bcrypt.GenerateFromPassword([]byte(body.Password), 10)
		if err != nil {
			ctx.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to hash password"})
			return
		}
		updates["password"] = string(hash)
	}

	if len(updates) == 0 {
		ctx.JSON(http.StatusBadRequest, gin.H{"error": "No fields to update"})
		return
	}

	if err := inits.DB.Model(&user).Updates(updates).Error; err != nil {
		ctx.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to update user"})
		return
	}

	ctx.JSON(http.StatusOK, gin.H{"data": user})
}


// Delete User
func DeleteUser(ctx *gin.Context) {
	uname := ctx.Param("username")

	result := inits.DB.Where("username = ?", uname).Delete(&models.User{})
	if result.Error != nil {
		ctx.JSON(500, gin.H{"error": result.Error.Error()})
		return
	}

	if result.RowsAffected == 0 {
		ctx.JSON(404, gin.H{"error": "user not found"})
		return
	}

	ctx.JSON(200, gin.H{"data": "user has been deleted successfully"})
}

