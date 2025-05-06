package com.example.trendbox;

import android.content.Intent;
import android.content.SharedPreferences;
import android.os.AsyncTask;
import android.os.Bundle;
import android.view.MenuItem;
import android.view.View;
import android.widget.ImageView;
import android.widget.PopupMenu;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

public class MainActivity extends AppCompatActivity {

    ImageView logoUser;
    TextView welcomeText;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        welcomeText = findViewById(R.id.welcome_main_pbx);
        logoUser = findViewById(R.id.logo_user);

        SharedPreferences prefs = getSharedPreferences("MyPrefs", MODE_PRIVATE);
        final String token = prefs.getString("jwt_token", null);
        if (token == null) {
            navigateToLogin();
            return;
        }

        logoUser.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                showUserMenu(v, token);
            }
        });

        // Panggil GetUserTask langsung saat MainActivity dibuka juga (bukan hanya saat klik logo)
        new GetUserTask(token).execute();
    }

    private void showUserMenu(View view, String token) {
        PopupMenu popup = new PopupMenu(MainActivity.this, view);
        popup.getMenuInflater().inflate(R.menu.user_menu, popup.getMenu());

        // Update menu username saat popup muncul
        new GetUserMenuTask(popup, token).execute();

        popup.setOnMenuItemClickListener(new PopupMenu.OnMenuItemClickListener() {
            @Override
            public boolean onMenuItemClick(MenuItem item) {
                if (item.getItemId() == R.id.menu_logout) {
                    logoutUser();
                    return true;
                }
                return false;
            }
        });

        popup.show();
    }

    private void logoutUser() {
        SharedPreferences prefs = getSharedPreferences("MyPrefs", MODE_PRIVATE);
        SharedPreferences.Editor editor = prefs.edit();
        editor.clear();
        editor.apply();

        Toast.makeText(this, "Logout berhasil", Toast.LENGTH_SHORT).show();
        navigateToLogin();
    }

    private void navigateToLogin() {
        Intent intent = new Intent(MainActivity.this, LoginActivity.class);
        intent.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(intent);
        finish();
    }

    // Non-static AsyncTask untuk update TextView di MainActivity
    private class GetUserTask extends AsyncTask<Void, Void, String> {
        private final String token;

        GetUserTask(String token) {
            this.token = token;
        }

        @Override
        protected String doInBackground(Void... voids) {
            try {
                URL url = new URL("http://spnj.my.id:8081/auth");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("GET");
                conn.setRequestProperty("Cookie", "Authorization=" + token);

                int responseCode = conn.getResponseCode();
                if (responseCode != 200) {
                    return "{\"username\":\"Unknown\"}";
                }

                BufferedReader reader = new BufferedReader(
                        new InputStreamReader(conn.getInputStream()));
                StringBuilder sb = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) {
                    sb.append(line);
                }
                reader.close();
                return sb.toString();
            } catch (Exception e) {
                e.printStackTrace();
                return "{\"username\":\"Unknown\"}";
            }
        }

        @Override
        protected void onPostExecute(String result) {
            try {
                JSONObject json = new JSONObject(result);
                JSONObject user = json.getJSONObject("user");
                String username = user.getString("Username");
                welcomeText.setText("Hi, " + username);
            } catch (JSONException e) {
                welcomeText.setText("Hi, Unknown");
            }
        }
    }

    // AsyncTask khusus untuk update PopupMenu username
    private class GetUserMenuTask extends AsyncTask<Void, Void, String> {
        private final PopupMenu popup;
        private final String token;

        GetUserMenuTask(PopupMenu popup, String token) {
            this.popup = popup;
            this.token = token;
        }

        @Override
        protected String doInBackground(Void... voids) {
            try {
                URL url = new URL("http://spnj.my.id:8081/auth");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("GET");
                conn.setRequestProperty("Cookie", "Authorization=" + token);

                int responseCode = conn.getResponseCode();
                if (responseCode != 200) {
                    return "{\"username\":\"Unknown\"}";
                }

                BufferedReader reader = new BufferedReader(
                        new InputStreamReader(conn.getInputStream()));
                StringBuilder sb = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) {
                    sb.append(line);
                }
                reader.close();
                return sb.toString();
            } catch (Exception e) {
                e.printStackTrace();
                return "{\"username\":\"Unknown\"}";
            }
        }

        @Override
        protected void onPostExecute(String result) {
            try {
                JSONObject json = new JSONObject(result);
                JSONObject user = json.getJSONObject("user");
                String username = user.getString("Username");
                popup.getMenu().findItem(R.id.menu_username).setTitle("\uD83D\uDC64 " + username);
            } catch (JSONException e) {
                popup.getMenu().findItem(R.id.menu_username).setTitle("\uD83D\uDC64 Unknown");
            }
        }
    }
}
