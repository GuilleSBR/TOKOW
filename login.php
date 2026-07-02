<?php
session_start();

// Configuración de la base de datos
$host = 'localhost';
$db_user = 'root'; // Cambia por tu usuario de MySQL
$db_pass = 'root';     // Cambia por tu contraseña de MySQL
$db_name = 'users';

$conn = new mysqli($host, $db_user, $db_pass, $db_name);

if ($conn->connect_error) {
    die("Error de conexión: " . $conn->connect_error);
}

$error = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $usuario = trim($_POST['usuario']);
    $contrasena = trim($_POST['contrasena']);

    if (!empty($usuario) && !empty($contrasena)) {
        // Usamos Prepared Statements para evitar Inyección SQL
        $stmt = $conn->prepare("SELECT usuario, contraseña FROM usuarios WHERE usuario = ?");
        $stmt->bind_param("s", $usuario);
        $stmt->execute();
        $result = $stmt->get_result();

        if ($result->num_rows === 1) {
            $row = $result->fetch_assoc();
            
            // NOTA: Si guardas contraseñas con password_hash() usa: if (password_verify($contrasena, $row['contraseña']))
            // Si están en texto plano (no recomendado), usa la comparación directa:
            if ($contrasena === $row['contraseña']) {
                $_SESSION['usuario'] = $row['usuario'];
                header("Location: index.php");
                exit();
            } else {
                $error = "Contraseña incorrecta.";
            }
        } else {
            $error = "El usuario no existe.";
        }
        $stmt->close();
    } else {
        $error = "Por favor, llena todos los campos.";
    }
}
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TOKOW - Iniciar Sesión</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
        body {
            background-color: #0D0E1C;
            color: #FFFFFF;
            font-family: 'Outfit', sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background-image: radial-gradient(circle at center, rgba(124, 111, 247, 0.15) 0%, transparent 70%);
        }
        .login-card {
            background: rgba(124, 111, 247, 0.06);
            border: 1px solid rgba(180, 174, 255, 0.12);
            border-radius: 16px;
            padding: 40px;
            width: 100%;
            max-width: 360px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
            backdrop-filter: blur(8px);
        }
        h2 { text-align: center; margin-bottom: 24px; font-weight: 700; letter-spacing: 1px; }
        .input-group { display: flex; flex-direction: column; gap: 8px; margin-bottom: 20px; }
        label { font-size: 12px; color: #B4AEFF; }
        input {
            background: rgba(13, 14, 28, 0.5);
            border: 1px solid rgba(180, 174, 255, 0.12);
            border-radius: 8px;
            padding: 12px;
            color: white;
            font-family: inherit;
            outline: none;
            transition: 0.2s;
        }
        input:focus { border-color: #7C6FF7; box-shadow: 0 0 0 3px rgba(124, 111, 247, 0.35); }
        .btn {
            width: 100%;
            background: linear-gradient(135deg, #7C6FF7, #5B4CEB);
            border: none;
            border-radius: 8px;
            padding: 12px;
            color: white;
            font-weight: 600;
            cursor: pointer;
            transition: 0.2s;
        }
        .btn:hover { filter: brightness(1.1); transform: translateY(-1px); }
        .error { color: #ef4444; font-size: 13px; text-align: center; margin-bottom: 15px; }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>TOKOW LOGIN</h2>
        <?php if(!empty($error)): ?>
            <div class="error"><?php echo $error; ?></div>
        <?php endif; ?>
        <form method="POST" action="">
            <div class="input-group">
                <label>Usuario</label>
                <input type="text" name="usuario" required autocomplete="off">
            </div>
            <div class="input-group">
                <label>Contraseña</label>
                <input type="password" name="contrasena" required>
            </div>
            <button type="submit" class="btn">Ingresar</button>
        </form>
    </div>
</body>
</html>