-- shopping_tracker_mcp schema

CREATE TABLE IF NOT EXISTS compras (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    quantidade FLOAT NOT NULL,
    unidade VARCHAR(50) DEFAULT 'unidade',
    wishlist BOOLEAN DEFAULT FALSE,
    ultima_compra DATE,
    preco FLOAT,
    supermercado VARCHAR(255),
    marca VARCHAR(255),
    volume_embalagem VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS wishlist (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    quantidade FLOAT NOT NULL,
    unidade VARCHAR(50) DEFAULT 'unidade',
    wishlist BOOLEAN DEFAULT TRUE,
    preco FLOAT,
    supermercado VARCHAR(255),
    marca VARCHAR(255),
    volume_embalagem VARCHAR(50)
);
