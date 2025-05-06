package com.example.trendbox;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.AsyncTask;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import org.json.JSONObject;

import java.io.BufferedWriter;
import java.io.OutputStream;
import java.io.OutputStreamWriter;
import java.net.HttpURLConnection;
import java.net.URL;

public class LoginActivity extends AppCompatActivity {

    EditText editUsername, editPassword;
    Button btnLogin;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_login);

        editUsername = findViewById(R.id.edit_username);
        editPassword = findViewById(R.id.edit_password);
        btnLogin = findViewById(R.id.btn_login);

        btnLogin.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                String username = editUsername.getText().toString().trim();
                String password = editPassword.getText().toString().trim();

                if (!username.isEmpty() && !password.isEmpty()) {
                    new LoginTask(LoginActivity.this).execute(username, password);
                } else {
                    Toast.makeText(LoginActivity.this, "Mohon isi semua field", Toast.LENGTH_SHORT).show();
                }
            }
        });
    }

    private static class LoginTask extends AsyncTask<String, Void, Boolean> {
        private Context context;
        private String token;
        private String errorMessage = "Login gagal. Silakan coba lagi.";

        LoginTask(Context context) {
            this.context = context;
        }

        @Override
        protected Boolean doInBackground(String... params) {
            String username = params[0];
            String password = params[1];

            try {
                URL url = new URL("http://spnj.my.id:8081/login");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setDoOutput(true);

                JSONObject jsonParam = new JSONObject();
                jsonParam.put("username", username);
                jsonParam.put("password", password);

                OutputStream os = conn.getOutputStream();
                BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(os, "UTF-8"));
                writer.write(jsonParam.toString());
                writer.flush();
                writer.close();
                os.close();

                int responseCode = conn.getResponseCode();
                if (responseCode == HttpURLConnection.HTTP_OK) {
                    String cookieHeader = conn.getHeaderField("Set-Cookie");
                    if (cookieHeader != null && cookieHeader.contains("Authorization=")) {
                        String[] cookies = cookieHeader.split(";");
                        for (String cookie : cookies) {
                            if (cookie.trim().startsWith("Authorization=")) {
                                token = cookie.trim().substring("Authorization=".length());
                                return true;
                            }
                        }
                    } else {
                        errorMessage = "Token tidak ditemukan dalam Set-Cookie.";
                    }
                } else {
                    errorMessage = "Login gagal dengan code: " + responseCode;
                }
            } catch (Exception e) {
                errorMessage = "Error: " + e.getMessage();
                e.printStackTrace();
            }
            return false;
        }

        @Override
        protected void onPostExecute(Boolean success) {
            if (success) {
                // Simpan token ke SharedPreferences
                SharedPreferences prefs = context.getSharedPreferences("MyPrefs", MODE_PRIVATE);
                SharedPreferences.Editor editor = prefs.edit();
                editor.putBoolean("is_logged_in", true);
                editor.putString("jwt_token", token);
                editor.apply();

                // Redirect ke MainActivity
                Intent intent = new Intent(context, MainActivity.class);
                intent.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_NEW_TASK);
                context.startActivity(intent);
                if (context instanceof LoginActivity) {
                    ((LoginActivity) context).finish();
                }
            } else {
                Toast.makeText(context, errorMessage, Toast.LENGTH_LONG).show();
            }
        }
    }
}
