package models

import "gorm.io/gorm"

type User struct {
	gorm.Model
	Username string `gorm:"type:varchar(100);unique"`
	Email    string `gorm:"type:varchar(100);unique"`
	Password string `gorm:"type:varchar(255)"`
	Role     int    `gorm:"default:4"`
}
