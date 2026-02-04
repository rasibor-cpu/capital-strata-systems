function login() {
  const user = document.getElementById("username").value;
  const pass = document.getElementById("password").value;
  const error = document.getElementById("error");

  if (user === "admin" && pass === "123456") {
    sessionStorage.setItem("rea_auth", "OK");
    window.location.href = "../index.html";
  } else {
    error.textContent = "Invalid credentials";
  }
}
